from __future__ import annotations

import secrets
import string


REFERRAL_PREFIX = "ref_"


def generate_referral_code(length: int = 10) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def extract_referral_code(start_argument: str | None) -> str | None:
    if not start_argument:
        return None

    payload = start_argument.strip()
    if not payload.startswith(REFERRAL_PREFIX):
        return None

    code = payload.removeprefix(REFERRAL_PREFIX).strip().upper()
    return code or None
