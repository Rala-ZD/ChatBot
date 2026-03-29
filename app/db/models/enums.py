from __future__ import annotations

from enum import StrEnum


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class PreferredGender(StrEnum):
    ANY = "any"
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class QueueStatus(StrEnum):
    WAITING = "waiting"
    MATCHED = "matched"
    CANCELLED = "cancelled"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"


class SessionEndReason(StrEnum):
    USER_END = "user_end"
    NEXT = "next"
    REPORT = "report"
    PARTNER_UNAVAILABLE = "partner_unavailable"
    INTERNAL_FAILURE = "internal_failure"
    MODERATION = "moderation"
    BLOCKED_BOT = "blocked_bot"


class MessageType(StrEnum):
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    VOICE = "voice"
    DOCUMENT = "document"
    STICKER = "sticker"


class ReportReason(StrEnum):
    SPAM = "spam"
    HARASSMENT = "harassment"
    NUDITY = "nudity"
    SCAM = "scam"
    UNDERAGE = "underage"
    OTHER = "other"
