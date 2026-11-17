"""Tenant-scoped PostgreSQL throttling shared by expensive legal AI endpoints."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    request_count: int
    retry_after_seconds: int


async def consume_chat_request(conn, organization_id: str, user_id: str,
                               requests_per_minute: int) -> RateLimitDecision:
    """Atomically consume one request from the current user's UTC minute bucket.

    The SQL operation is safe under concurrent API workers. Only counters and
    timestamps are stored; question text and other conversation content are not.
    """
    if not 1 <= requests_per_minute <= 120:
        raise ValueError("La limite de requêtes chat doit être comprise entre 1 et 120.")

    row = await conn.fetchrow(
        """
        INSERT INTO chat_rate_limit_buckets
            (organization_id,user_id,window_start,request_count)
        VALUES ($1::uuid,$2::uuid,date_trunc('minute',clock_timestamp()),1)
        ON CONFLICT (organization_id,user_id,window_start)
        DO UPDATE SET request_count=LEAST(
            chat_rate_limit_buckets.request_count+1,$3+1
        )
        RETURNING request_count,
            GREATEST(1,CEIL(EXTRACT(EPOCH FROM
                (window_start+interval '1 minute'-clock_timestamp())))::integer)
                AS retry_after_seconds
        """,
        organization_id, user_id, requests_per_minute,
    )
    # Keep at most one day of counter history per user. This never touches
    # messages, conversations, legal dossiers or audit records.
    await conn.execute(
        """
        DELETE FROM chat_rate_limit_buckets
        WHERE organization_id=$1::uuid AND user_id=$2::uuid
          AND window_start < date_trunc('minute',clock_timestamp())-interval '1 day'
        """,
        organization_id, user_id,
    )
    count = int(row["request_count"])
    return RateLimitDecision(
        allowed=count <= requests_per_minute,
        request_count=count,
        retry_after_seconds=int(row["retry_after_seconds"]),
    )
