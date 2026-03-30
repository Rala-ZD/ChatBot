from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session_rating import SessionRating


class SessionRatingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_if_absent(self, rating: SessionRating) -> bool:
        statement = (
            insert(SessionRating)
            .values(
                session_id=rating.session_id,
                from_user_id=rating.from_user_id,
                to_user_id=rating.to_user_id,
                value=rating.value,
                created_at=rating.created_at,
            )
            .on_conflict_do_nothing(
                index_elements=["session_id", "from_user_id"],
            )
            .returning(SessionRating.id)
        )
        result = await self.session.execute(statement)
        inserted_id = result.scalar_one_or_none()
        if inserted_id is None:
            return False
        rating.id = inserted_id
        return True
