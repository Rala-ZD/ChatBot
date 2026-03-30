from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.db.models.session_rating import SessionRating
from app.db.repositories.session_rating_repository import SessionRatingRepository
from app.db.repositories.session_repository import SessionRepository
from app.db.repositories.user_repository import UserRepository
from app.services.exceptions import AccessDeniedError, ConflictError, NotFoundError
from app.utils.enums import SessionRatingValue, SessionStatus
from app.utils.time import utcnow

RATING_STEP = Decimal("0.2")
RATING_MIN = Decimal("-5.0")
RATING_MAX = Decimal("5.0")
RATING_QUANTUM = Decimal("0.1")


@dataclass(slots=True)
class RatingSaveResult:
    already_saved: bool


class RatingService:
    def __init__(
        self,
        session_repository: SessionRepository,
        session_rating_repository: SessionRatingRepository,
        user_repository: UserRepository,
    ) -> None:
        self.session_repository = session_repository
        self.session_rating_repository = session_rating_repository
        self.user_repository = user_repository

    async def save_rating(
        self,
        session_id: int,
        from_user_id: int,
        value: SessionRatingValue,
    ) -> RatingSaveResult:
        chat_session = await self.session_repository.get_with_details(session_id)
        if chat_session is None:
            raise NotFoundError("Chat not found.")

        if from_user_id not in {chat_session.user1_id, chat_session.user2_id}:
            raise AccessDeniedError("You can only rate your own chats.")
        if chat_session.status != SessionStatus.ENDED or chat_session.ended_at is None:
            raise ConflictError("You can rate this chat after it ends.")

        rated_user_id = chat_session.partner_id_for(from_user_id)
        created = await self.session_rating_repository.create_if_absent(
            SessionRating(
                session_id=session_id,
                from_user_id=from_user_id,
                to_user_id=rated_user_id,
                value=value,
                created_at=utcnow(),
            )
        )
        if not created:
            return RatingSaveResult(already_saved=True)

        rated_user = await self.user_repository.get_by_id_for_update(rated_user_id)
        if rated_user is None:
            raise NotFoundError("User not found.")

        current_score = rated_user.rating_score if rated_user.rating_score is not None else Decimal("0.0")
        delta = RATING_STEP if value == SessionRatingValue.GOOD else -RATING_STEP
        rated_user.rating_score = self._clamp_score(current_score + delta)
        await self.user_repository.save(rated_user)
        await self.user_repository.session.commit()
        return RatingSaveResult(already_saved=False)

    def _clamp_score(self, score: Decimal) -> Decimal:
        bounded = min(RATING_MAX, max(RATING_MIN, score))
        return bounded.quantize(RATING_QUANTUM)
