import pytest

from app.rate_limit import consume_chat_request


class FakeConnection:
    def __init__(self, count: int, retry_after: int = 30):
        self.count = count
        self.retry_after = retry_after
        self.statements = []

    async def fetchrow(self, query, *args):
        self.statements.append(query)
        assert args[2] == 10
        return {"request_count": self.count, "retry_after_seconds": self.retry_after}

    async def execute(self, query, *args):
        self.statements.append(query)
        assert "window_start <" in query


@pytest.mark.asyncio
async def test_chat_rate_limit_allows_requests_under_limit_and_cleans_old_buckets():
    conn = FakeConnection(count=10)
    decision = await consume_chat_request(conn, "org-id", "user-id", 10)
    assert decision.allowed is True
    assert decision.request_count == 10
    assert decision.retry_after_seconds == 30
    assert len(conn.statements) == 2


@pytest.mark.asyncio
async def test_chat_rate_limit_rejects_the_first_request_over_limit():
    conn = FakeConnection(count=11, retry_after=17)
    decision = await consume_chat_request(conn, "org-id", "user-id", 10)
    assert decision.allowed is False
    assert decision.request_count == 11
    assert decision.retry_after_seconds == 17


@pytest.mark.asyncio
async def test_chat_rate_limit_rejects_invalid_configuration():
    with pytest.raises(ValueError, match="comprise"):
        await consume_chat_request(FakeConnection(1), "org-id", "user-id", 0)
