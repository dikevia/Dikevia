"""Tenant-scoped PostgreSQL throttling shared by expensive legal and AI connector endpoints."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    request_count: int
    retry_after_seconds: int


async def consume_chat_request(conn, organization_id: str, user_id: str,
                               requests_per_minute: int) -> RateLimitDecision:
    """Atomically consume one expensive legal request from the current user's UTC minute bucket.

    The SQL operation is safe under concurrent API workers. Only counters and
    timestamps are stored; question text, search terms and other user content are not.
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



@dataclass(frozen=True)
class DailyQuestionDecision:
    allowed: bool
    question_count: int


async def consume_daily_chat_question(
    conn, organization_id: str, user_id: str, daily_limit: int = 5,
) -> DailyQuestionDecision:
    """Atomically consume one Agent question in the Europe/Paris calendar day."""
    if not 1 <= daily_limit <= 5:
        raise ValueError("Le quota quotidien doit être compris entre 1 et 5.")

    row = await conn.fetchrow(
        """
        INSERT INTO chat_daily_question_usage
            (organization_id,user_id,usage_date,question_count)
        VALUES (
            $1::uuid,$2::uuid,(clock_timestamp() AT TIME ZONE 'Europe/Paris')::date,1
        )
        ON CONFLICT (organization_id,user_id,usage_date)
        DO UPDATE SET
            question_count=chat_daily_question_usage.question_count+1,
            updated_at=now()
        WHERE chat_daily_question_usage.question_count < $3
        RETURNING question_count
        """,
        organization_id, user_id, daily_limit,
    )
    if row:
        return DailyQuestionDecision(True, int(row["question_count"]))

    current_count = await conn.fetchval(
        """
        SELECT question_count FROM chat_daily_question_usage
        WHERE organization_id=$1::uuid AND user_id=$2::uuid
          AND usage_date=(clock_timestamp() AT TIME ZONE 'Europe/Paris')::date
        """,
        organization_id, user_id,
    )
    return DailyQuestionDecision(False, int(current_count or 0))
