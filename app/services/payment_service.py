from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from aiogram.types import LabeledPrice, PreCheckoutQuery, SuccessfulPayment

from app.config import Settings
from app.db.models.point_purchase import PointPurchase
from app.db.models.user import User
from app.db.repositories.point_purchase_repository import PointPurchaseRepository
from app.db.repositories.user_repository import UserRepository
from app.services.exceptions import ValidationError
from app.services.ops_service import OpsService
from app.logging import get_logger
from app.utils.enums import PointPurchaseStatus
from app.utils.time import utcnow


@dataclass(frozen=True, slots=True)
class PointsPackage:
    code: str
    points_amount: int
    stars_amount: int

    @property
    def button_label(self) -> str:
        return f"{self.points_amount} pts"

    @property
    def invoice_title(self) -> str:
        return f"{self.points_amount} Points"

    @property
    def invoice_description(self) -> str:
        return f"Top up your wallet with {self.points_amount} points using Telegram Stars."


@dataclass(frozen=True, slots=True)
class InvoiceRequest:
    title: str
    description: str
    payload: str
    currency: str
    prices: list[LabeledPrice]
    start_parameter: str


@dataclass(frozen=True, slots=True)
class PreCheckoutValidation:
    ok: bool
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class PurchaseResult:
    user: User
    points_added: int
    already_processed: bool


class PaymentService:
    def __init__(
        self,
        settings: Settings,
        user_repository: UserRepository,
        point_purchase_repository: PointPurchaseRepository,
        ops_service: OpsService,
    ) -> None:
        self.settings = settings
        self.user_repository = user_repository
        self.point_purchase_repository = point_purchase_repository
        self.ops_service = ops_service
        self.logger = get_logger(__name__)

    def payments_enabled(self) -> bool:
        return self.settings.payments_enabled

    def list_packages(self) -> tuple[PointsPackage, ...]:
        if not self.payments_enabled():
            raise ValidationError("Telegram Stars checkout is unavailable right now.")

        prices = {
            10: self.settings.points_package_10_xtr,
            50: self.settings.points_package_50_xtr,
            150: self.settings.points_package_150_xtr,
        }
        return tuple(
            PointsPackage(
                code=f"points_{points_amount}",
                points_amount=points_amount,
                stars_amount=stars_amount,
            )
            for points_amount, stars_amount in prices.items()
            if stars_amount is not None
        )

    def get_package(self, package_code: str) -> PointsPackage:
        for package in self.list_packages():
            if package.code == package_code:
                return package
        raise ValidationError("That Stars pack is unavailable.")

    async def create_invoice_request(self, user: User, package_code: str) -> InvoiceRequest:
        if not user.is_registered:
            raise ValidationError("Finish setup with /start first.")

        package = self.get_package(package_code)
        payload = f"points:{package.code}:{uuid4().hex}"
        purchase = PointPurchase(
            user_id=user.id,
            package_code=package.code,
            points_amount=package.points_amount,
            total_amount_minor=package.stars_amount,
            currency=self.settings.payments_currency,
            invoice_payload=payload,
            status=PointPurchaseStatus.PENDING,
        )
        await self.point_purchase_repository.create(purchase)
        await self.point_purchase_repository.session.commit()

        return InvoiceRequest(
            title=package.invoice_title,
            description=package.invoice_description,
            payload=payload,
            currency=self.settings.payments_currency,
            prices=[LabeledPrice(label=package.invoice_title, amount=package.stars_amount)],
            start_parameter=f"buy-{package.code}",
        )

    async def validate_pre_checkout(self, query: PreCheckoutQuery) -> PreCheckoutValidation:
        if not self.payments_enabled():
            return PreCheckoutValidation(ok=False, error_message="Telegram Stars checkout is unavailable right now.")

        purchase = await self.point_purchase_repository.get_by_invoice_payload(query.invoice_payload)
        if purchase is None:
            return PreCheckoutValidation(ok=False, error_message="This payment could not be verified.")
        if purchase.status != PointPurchaseStatus.PENDING:
            return PreCheckoutValidation(ok=False, error_message="This payment was already processed.")
        if purchase.currency != query.currency.upper() or purchase.total_amount_minor != query.total_amount:
            return PreCheckoutValidation(ok=False, error_message="This payment does not match the selected pack.")

        user = await self.user_repository.get_by_id(purchase.user_id)
        if user is None or user.telegram_id != query.from_user.id:
            return PreCheckoutValidation(ok=False, error_message="This payment does not belong to this account.")

        return PreCheckoutValidation(ok=True)

    async def finalize_successful_payment(
        self,
        user: User,
        successful_payment: SuccessfulPayment,
    ) -> PurchaseResult:
        purchase = await self.point_purchase_repository.get_by_invoice_payload_for_update(
            successful_payment.invoice_payload
        )
        if purchase is None:
            raise ValidationError("Payment could not be verified.")
        if purchase.user_id != user.id:
            raise ValidationError("Payment does not match this account.")
        if purchase.currency != successful_payment.currency.upper() or (
            purchase.total_amount_minor != successful_payment.total_amount
        ):
            raise ValidationError("Payment details do not match the selected pack.")

        locked_user = await self.user_repository.get_by_id_for_update(user.id)
        if locked_user is None:
            raise ValidationError("Payment could not be verified.")

        if purchase.status == PointPurchaseStatus.PAID:
            await self.point_purchase_repository.session.commit()
            return PurchaseResult(
                user=locked_user,
                points_added=0,
                already_processed=True,
            )

        locked_user.points_balance += purchase.points_amount
        purchase.telegram_payment_charge_id = successful_payment.telegram_payment_charge_id or None
        purchase.provider_payment_charge_id = successful_payment.provider_payment_charge_id or None
        purchase.status = PointPurchaseStatus.PAID
        purchase.credited_at = utcnow()

        await self.user_repository.save(locked_user)
        await self.point_purchase_repository.save(purchase)
        await self.point_purchase_repository.session.commit()
        await self.ops_service.record_payment_success()
        self.logger.info(
            "payment_credited",
            user_id=user.id,
            points_added=purchase.points_amount,
            purchase_id=purchase.id,
        )

        return PurchaseResult(
            user=locked_user,
            points_added=purchase.points_amount,
            already_processed=False,
        )
