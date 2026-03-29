from __future__ import annotations

from enum import StrEnum


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class PreferredGender(StrEnum):
    ANY = "any"
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class QueueStatus(StrEnum):
    WAITING = "waiting"
    MATCHED = "matched"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"


class EndReason(StrEnum):
    END = "end"
    NEXT = "next"
    REPORT = "report"
    PARTNER_UNREACHABLE = "partner_unreachable"
    MODERATION = "moderation"
    INTERNAL_FAILURE = "internal_failure"


class MessageType(StrEnum):
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    VOICE = "voice"
    DOCUMENT = "document"
    STICKER = "sticker"
    UNSUPPORTED = "unsupported"


class DeliveryStatus(StrEnum):
    DELIVERED = "delivered"
    FAILED = "failed"


class PointPurchaseStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
