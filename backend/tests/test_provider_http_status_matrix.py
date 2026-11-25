"""Regression matrix for transient and non-transient AI provider HTTP failures."""
import httpx
import pytest

from app import ai_provider
from app.config import settings


class SequenceClient:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.models = []

    async def post(self, url, *, headers, json):
        self.models.append(json.get("model"))
        status = self.statuses.pop(0)
        return httpx.Response(
            status,
            request=httpx.Request("POST", url),
            json={"error": {"message": "synthetic provider response"}},
        )


async def _no_wait(_seconds):
    return None


@pytest.fixture(autouse=True)
def _gemini_provider(monkeypatch):
    monkeypatch.setattr(
        settings,
        "ai_api_base_url",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    )
    monkeypatch.setattr(settings, "ai_fallback_models", "gemini-2.5-flash-lite")
    monkeypatch.setattr(ai_provider.asyncio, "sleep", _no_wait)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429])
async def test_auth_and_quota_failures_are_not_retried_or_sent_to_fallback(status):
    client = SequenceClient([status, 200])
    payload = {"model": "gemini-2.5-flash"}

    with pytest.raises(httpx.HTTPStatusError) as error:
        await ai_provider._post_chat_completion(
            client,
            "https://example.test/v1/chat/completions",
            headers={"Authorization": "Bearer test-only"},
            payload=payload,
        )

    assert error.value.response.status_code == status
    assert client.models == ["gemini-2.5-flash"]


@pytest.mark.asyncio
async def test_http_500_retries_primary_once_but_does_not_switch_models():
    client = SequenceClient([500, 500, 200])
    payload = {"model": "gemini-2.5-flash"}

    with pytest.raises(httpx.HTTPStatusError) as error:
        await ai_provider._post_chat_completion(
            client,
            "https://example.test/v1/chat/completions",
            headers={"Authorization": "Bearer test-only"},
            payload=payload,
        )

    assert error.value.response.status_code == 500
    assert client.models == ["gemini-2.5-flash", "gemini-2.5-flash"]


@pytest.mark.asyncio
async def test_http_503_retries_primary_then_uses_one_configured_fallback():
    client = SequenceClient([503, 503, 200])
    payload = {"model": "gemini-2.5-flash"}

    response = await ai_provider._post_chat_completion(
        client,
        "https://example.test/v1/chat/completions",
        headers={"Authorization": "Bearer test-only"},
        payload=payload,
    )

    assert response.status_code == 200
    assert client.models == [
        "gemini-2.5-flash",
        "gemini-2.5-flash",
        "gemini-3.5-flash-lite",
    ]
