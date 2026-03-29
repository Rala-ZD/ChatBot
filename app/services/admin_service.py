from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.repositories.report_repository import ReportRepository
from app.db.session import session_scope
from app.schemas.api import (
    ReportResponse,
    SessionDetailResponse,
    SessionMessageResponse,
    UserSummaryResponse,
)
from app.services.export_service import ExportService
from app.utils.exceptions import UserVisibleError


class AdminService:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        export_service: ExportService,
    ) -> None:
        self.session_factory = session_factory
        self.export_service = export_service

    async def list_reports(self, limit: int = 50) -> list[ReportResponse]:
        async with session_scope(self.session_factory) as session:
            repo = ReportRepository(session)
            reports = await repo.list_recent(limit=limit)
        return [
            ReportResponse(
                id=report.id,
                session_id=report.session_id,
                reporter_user_id=report.reporter_user_id,
                reported_user_id=report.reported_user_id,
                reason=str(report.reason),
                note=report.note,
                created_at=report.created_at,
            )
            for report in reports
        ]

    async def get_session_detail(self, session_id: uuid.UUID) -> SessionDetailResponse:
        bundle = await self.export_service.load_bundle(session_id)
        if bundle is None:
            raise UserVisibleError("Session not found.")
        return SessionDetailResponse(
            session_id=bundle.session.id,
            status=str(bundle.session.status),
            started_at=bundle.session.started_at,
            ended_at=bundle.session.ended_at,
            end_reason=str(bundle.session.end_reason) if bundle.session.end_reason else None,
            user1=UserSummaryResponse(
                id=bundle.user1.id,
                telegram_id=bundle.user1.telegram_id,
                username=bundle.user1.username,
                first_name=bundle.user1.first_name,
                nickname=bundle.user1.nickname,
                age=bundle.user1.age,
                gender=bundle.user1.gender.value if bundle.user1.gender else None,
                preferred_gender=bundle.user1.preferred_gender.value if bundle.user1.preferred_gender else None,
                interests=bundle.user1.interests_json,
                is_registered=bundle.user1.is_registered,
                is_banned=bundle.user1.is_banned,
            ),
            user2=UserSummaryResponse(
                id=bundle.user2.id,
                telegram_id=bundle.user2.telegram_id,
                username=bundle.user2.username,
                first_name=bundle.user2.first_name,
                nickname=bundle.user2.nickname,
                age=bundle.user2.age,
                gender=bundle.user2.gender.value if bundle.user2.gender else None,
                preferred_gender=bundle.user2.preferred_gender.value if bundle.user2.preferred_gender else None,
                interests=bundle.user2.interests_json,
                is_registered=bundle.user2.is_registered,
                is_banned=bundle.user2.is_banned,
            ),
            messages=[
                SessionMessageResponse(
                    id=message.id,
                    sender_user_id=message.sender_user_id,
                    message_type=str(message.message_type),
                    telegram_message_id=message.telegram_message_id,
                    text_content=message.text_content,
                    caption=message.caption,
                    file_id=message.file_id,
                    created_at=message.created_at,
                )
                for message in bundle.messages
            ],
        )
