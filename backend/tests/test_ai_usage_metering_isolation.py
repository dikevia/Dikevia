import pytest


class _FakeTransaction:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        self.connection.transaction_entered += 1
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.connection.transaction_exited += 1
        self.connection.transaction_error = exc_type
        return False


class _FailingConnection:
    def __init__(self):
        self.transaction_entered = 0
        self.transaction_exited = 0
        self.transaction_error = None
        self.execute_calls = 0

    def transaction(self):
        return _FakeTransaction(self)

    async def execute(self, *_args):
        self.execute_calls += 1
        raise RuntimeError("simulated metering database failure")


@pytest.mark.asyncio
async def test_metering_failure_is_isolated_and_does_not_escape_to_request():
    from app.main import record_ai_usage_event

    connection = _FailingConnection()
    usage = {
        "provider": "test",
        "model": "test-model",
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "outcome": "ANSWERED",
    }

    # A failed telemetry INSERT must not turn a completed legal response into HTTP 500.
    await record_ai_usage_event(
        connection,
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000003",
        usage,
    )

    assert connection.transaction_entered == 1
    assert connection.transaction_exited == 1
    assert connection.transaction_error is RuntimeError
    assert connection.execute_calls == 1
