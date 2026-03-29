from __future__ import annotations


def waiting_queue_members_key() -> str:
    return "queue:waiting:members"


def matchmaking_lock_key() -> str:
    return "lock:matchmaking"


def relay_lock_key(session_id: str) -> str:
    return f"lock:relay:{session_id}"


def session_end_lock_key(session_id: str) -> str:
    return f"lock:session:end:{session_id}"


def session_export_lock_key(session_id: str) -> str:
    return f"lock:session:export:{session_id}"


def rate_limit_key(scope: str, user_id: int) -> str:
    return f"ratelimit:{scope}:{user_id}"
