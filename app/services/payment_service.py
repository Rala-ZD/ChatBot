from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from aiogram.types import LabeledPrice, PreCheckoutQuery, SuccessfulPayment

from app.config import Settings
from app.db.models.point_purchase import PointPurchase
from app.db.models.user import User
from app.db.repositories.point_purchase_repository import PointPurchaseRepository
from app.db.repositories.user_repository import UserRepository
from app.services.exceptions import ValidationError
from app.services.ops_service import OpsService
from app.services.user_service import extend_vip_access
from app.logging import get_logger
from app.utils.enums import PointPurchaseStatus
from app.utils.time import utcnow

VIP_WEEK_DAYS = 7
VIP_MONTH_DAYS = 30
VIP_6MONTHS_DAYS = 180


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
class VipPlan:
    code: str
    title: str
    days: int
    stars_amount: int

    @property
    def duration(self) -> timedelta:
        return timedelta(days=self.days)

    @property
    def invoice_title(self) -> str:
        return self.title

    @property
    def invoice_description(self) -> str:
        return f"Unlock Premium Matching for {self.title.lower()} using Telegram Stars."


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
    package_code: str
    purchase_kind: str
    vip_was_extended: bool = False


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

    def list_vip_plans(self) -> tuple[VipPlan, ...]:
        if not self.payments_enabled():
            raise ValidationError("Telegram Stars checkout is unavailable right now.")

        plans = (
            VipPlan(
                code="vip_week",
                title="VIP 1 Week",
                days=VIP_WEEK_DAYS,
                stars_amount=self.settings.vip_week_xtr,
            ),
            VipPlan(
                code="vip_month",
                title="VIP 1 Month",
                days=VIP_MONTH_DAYS,
                stars_amount=self.settings.vip_month_xtr,
            ),
            VipPlan(
                code="vip_6months",
                title="VIP 6 Months",
                days=VIP_6MONTHS_DAYS,
                stars_amount=self.settings.vip_6months_xtr,
            ),
        )
        return tuple(plan for plan in plans if plan.stars_amount is not None)

    def get_vip_plan(self, plan_code: str) -> VipPlan:
        for plan in self.list_vip_plans():
            if plan.code == plan_code:
                return plan
        raise ValidationError("That VIP plan is unavailable.")

    def _is_vip_plan(self, product_code: str) -> bool:
        return product_code.startswith("vip_")

    async def create_invoice_request(self, user: User, package_code: str) -> InvoiceRequest:
        if not user.is_registered:
            raise ValidationError("Finish setup with /start first.")

        if self._is_vip_plan(package_code):
            plan = self.get_vip_plan(package_code)
            payload = f"vip:{plan.code}:{uuid4().hex}"
            purchase = PointPurchase(
                user_id=user.id,
                package_code=plan.code,
                points_amount=0,
                total_amount_minor=plan.stars_amount,
                currency=self.settings.payments_currency,
                invoice_payload=payload,
                status=PointPurchaseStatus.PENDING,
            )
            title = plan.invoice_title
            description = plan.invoice_description
            total_amount_minor = plan.stars_amount
            start_parameter = f"buy-{plan.code}"
        else:
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
            title = package.invoice_title
            description = package.invoice_description
            total_amount_minor = package.stars_amount
            start_parameter = f"buy-{package.code}"

        await self.point_purchase_repository.create(purchase)
        await self.point_purchase_repository.session.commit()

        return InvoiceRequest(
            title=title,
            description=description,
            payload=payload,
            currency=self.settings.payments_currency,
            prices=[LabeledPrice(label=title, amount=total_amount_minor)],
            start_parameter=start_parameter,
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
                package_code=purchase.package_code,
                purchase_kind="vip" if self._is_vip_plan(purchase.package_code) else "points",
            )

        purchase_kind = "vip" if self._is_vip_plan(purchase.package_code) else "points"
        vip_was_extended = False
        if purchase_kind == "vip":
            plan = self.get_vip_plan(purchase.package_code)
            vip_was_extended = locked_user.has_active_vip()
            extend_vip_access(locked_user, plan.duration)
        else:
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
            purchase_kind=purchase_kind,
            package_code=purchase.package_code,
            points_added=purchase.points_amount,
            purchase_id=purchase.id,
        )

        return PurchaseResult(
            user=locked_user,
            points_added=purchase.points_amount,
            already_processed=False,
            package_code=purchase.package_code,
            purchase_kind=purchase_kind,
            vip_was_extended=vip_was_extended,
        )
