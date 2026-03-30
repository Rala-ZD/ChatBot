from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from datetime import datetime

from app.utils.enums import PreferredGender
from app.utils.time import humanize_duration, utcnow


SELECT_GENDER_BUTTON_TEXT = "\U0001f3af Select Gender"
SEARCH_CANCEL_BUTTON_TEXT = "\u274c Cancel"
BUY_POINTS_BUTTON_TEXT = "\U0001f4b3 Buy Points"
FREE_BUTTON_TEXT = "Free"

WELCOME_TEXT = (
    "\U0001f4ac Anonymous Chat\n\n"
    "Meet someone new in seconds.\n"
    "Your identity stays private."
)

RETURNING_HOME_TEXT = (
    "\U0001f4ac Anonymous Chat\n\n"
    "Ready for the next match?\n"
    "Tap Start Chat to jump in."
)

RULES_TEXT = (
    "\U0001f6e1\ufe0f Safety\n\n"
    "Be respectful\n"
    "No spam or explicit content\n"
    "Share only what you want\n"
    "Use /report if needed\n\n"
    "Continue only if you meet the age requirement."
)

HELP_TEXT = (
    "\U0001f9ed Help\n\n"
    "Basics\n"
    "/start Open the bot\n"
    "/profile Edit your profile\n"
    "/selectgender Open the premium filter\n\n"
    "Rewards\n"
    "/invite Earn points\n"
    "/points Open your wallet\n"
    "/vip Unlock premium\n\n"
    "Chat\n"
    "/next Next match\n"
    "/end End chat\n"
    "/report Report chat\n"
    "/cancel Cancel search or form"
)

SEARCHING_TEXT = "\U0001f50e Looking for a match...\nTap \u274c Cancel to stop."
SEARCH_CANCELLED_TEXT = "\U0001f6d1 Search cancelled\nYou can try again anytime."
NO_ACTIVE_SEARCH_TEXT = "No active search."
SEARCH_MATCHED_TEXT = "\U0001f389 Match Found\nYou're connected."
NO_ACTIVE_CHAT_TEXT = "No active chat."
CHAT_COMMAND_HINT_TEXT = "Use /next, /end, or /report."
EARLY_CHAT_RESTRICTION_TEXT = (
    "\U0001f512 This opens after the first 90 seconds\n"
    "\u2b50 Premium users can share instantly"
)
REPORT_PROMPT_TEXT = "\U0001f6a9 Report Chat\n\nSend a short reason."
REPORT_DONE_TEXT = "\U0001f6a9 Report Chat\n\nReport sent.\nChat closed."
FEEDBACK_SAVED_TEXT = "\u2705 Feedback saved"
FEEDBACK_ALREADY_SAVED_TEXT = "Feedback already saved"
INVITE_UNAVAILABLE_TEXT = "Invite link unavailable."
VIP_POINTS_REQUIRED_TEXT = "Need 10 points.\nUse /invite to earn more."
PAYMENTS_UNAVAILABLE_TEXT = "\U0001f4b3 Buy Points\n\nTelegram Stars checkout is unavailable.\nTry again later."


def normalize_interests(raw_value: str) -> list[str]:
    if not raw_value.strip():
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for item in raw_value.split(","):
        cleaned = item.strip().lower()
        if not cleaned:
            continue
        if not (2 <= len(cleaned) <= 20):
            raise ValueError("Each interest must be between 2 and 20 characters.")
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
        if len(normalized) > 10:
            raise ValueError("You can add up to 10 interests.")
    return normalized


def format_interests(interests: Iterable[str]) -> str:
    items = list(interests)
    return ", ".join(items) if items else "Not set"


def format_rating_score(rating_score: Decimal | None) -> str:
    if rating_score is None:
        return "new"
    return f"{Decimal(rating_score).quantize(Decimal('0.1'))}"


def build_match_found_text(
    partner_interests: Iterable[str],
    partner_rating_score: Decimal | None,
) -> str:
    formatted_interests = ", ".join(item.title() for item in partner_interests if item.strip())
    interests_text = formatted_interests or "not set"
    return (
        "\U0001f436 Partner found!\n\n"
        "/next - next chat\n"
        "/end - stop chat\n\n"
        f"\U0001f4da Interests: {interests_text}\n"
        f"\U0001f3c6 Rating: {format_rating_score(partner_rating_score)}\n\n"
        "\U0001f4a1 Hint: start with something simple \U0001f609"
    )


def build_chat_summary_text(
    started_at: datetime,
    ended_at: datetime | None,
    message_count: int,
) -> str:
    return (
        "Chat ended\n\n"
        f"Duration: {humanize_duration(started_at, ended_at)}\n"
        f"Messages: {message_count}\n\n"
        "How was this chat?"
    )


def format_preferred_gender(value: str | PreferredGender) -> str:
    preferred = PreferredGender(value)
    return "Anyone" if preferred == PreferredGender.ANY else preferred.value.title()


def format_datetime_short(value: datetime) -> str:
    return value.astimezone().strftime("%d %b %H:%M")


def format_premium_access_status(vip_until: datetime | None) -> str:
    if vip_until is not None and vip_until > utcnow():
        return f"Active until {format_datetime_short(vip_until)}"
    return "Locked"


def build_invite_text(bot_username: str, referral_code: str) -> str:
    link = f"https://t.me/{bot_username}?start=ref_{referral_code}"
    return (
        "\U0001f381 Invite Friends\n\n"
        "Earn 5 points for every friend\n"
        "who finishes setup.\n\n"
        f"Your link\n{link}"
    )


def build_points_status_text(points_balance: int, vip_until: datetime | None) -> str:
    return (
        "\U0001f4b0 Points Wallet\n\n"
        f"Balance: {points_balance} points\n"
        f"Premium: {format_premium_access_status(vip_until)}\n\n"
        "Top up with Stars or earn them free."
    )


def build_buy_points_text(points_balance: int, vip_until: datetime | None) -> str:
    return (
        "\U0001f4b3 Buy Points\n\n"
        f"Balance: {points_balance} points\n"
        f"Premium: {format_premium_access_status(vip_until)}\n\n"
        "Choose a Telegram Stars pack."
    )


def build_points_purchase_success_text(
    points_added: int,
    points_balance: int,
    vip_until: datetime | None,
) -> str:
    return (
        "\U0001f4b0 Points Wallet\n\n"
        f"Added: {points_added} points\n"
        f"Balance: {points_balance} points\n"
        f"Premium: {format_premium_access_status(vip_until)}\n\n"
        "Paid with Telegram Stars."
    )


def build_vip_unlocked_text(points_balance: int, vip_until: datetime | None) -> str:
    return (
        "\u2b50 Premium Active\n\n"
        f"Balance: {points_balance} points\n"
        f"Premium: {format_premium_access_status(vip_until)}\n\n"
        "Use /selectgender to set your filter."
    )


def build_premium_gender_gate_text(points_balance: int, cost_points: int) -> str:
    return (
        "\u2728 Select Gender\n\n"
        "Choose who you'd rather match with.\n"
        "Upgrade for sharper matching.\n\n"
        f"Balance: {points_balance} points\n"
        f"Unlock: {cost_points} points / 1 day"
    )


def build_gender_selection_text(
    preferred_gender: str | PreferredGender,
    vip_until: datetime | None,
    *,
    success: bool = False,
) -> str:
    prefix = "Unlocked.\n\n" if success else ""
    return (
        f"{prefix}"
        "\u2b50 Premium Active\n\n"
        f"Filter: {format_preferred_gender(preferred_gender)}\n"
        f"Premium: {format_premium_access_status(vip_until)}\n\n"
        "Pick who you'd like to meet."
    )


def chunk_text(text: str, chunk_size: int = 3500) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= chunk_size:
            chunks.append(remaining)
            break

        split_at = remaining.rfind("\n", 0, chunk_size)
        if split_at == -1:
            split_at = chunk_size
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    return chunks
