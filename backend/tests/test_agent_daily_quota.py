import pytest

from app.rate_limit import consume_daily_chat_question


class FakeDailyConnection:
    def __init__(self, rows, current_count=0):
        self.rows = list(rows)
        self.current_count = current_count
        self.fetchrow_calls = []
        self.fetchval_calls = []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query, args))
        return self.rows.pop(0)

    async def fetchval(self, query, *args):
        self.fetchval_calls.append((query, args))
        return self.current_count


@pytest.mark.asyncio
async def test_daily_agent_question_quota_allows_five_and_rejects_sixth():
    conn = FakeDailyConnection(
        [{"question_count": count} for count in range(1, 6)] + [None],
        current_count=5,
    )
    decisions = [
        await consume_daily_chat_question(conn, "user", 5)
        for _ in range(6)
    ]
    assert [item.allowed for item in decisions] == [True, True, True, True, True, False]
    assert [item.question_count for item in decisions] == [1, 2, 3, 4, 5, 5]
    assert "Europe/Paris" in conn.fetchrow_calls[0][0]
    assert "question_count < $2" in conn.fetchrow_calls[0][0]
    assert conn.fetchval_calls


@pytest.mark.asyncio
async def test_daily_agent_question_quota_rejects_invalid_limit():
    with pytest.raises(ValueError, match="compris entre 1 et 5"):
        await consume_daily_chat_question(FakeDailyConnection([]), "user", 6)
