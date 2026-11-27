"""Regression tests for Gemini retired-model and fallback handling."""
import json

import httpx
import pytest

from app import ai_provider
from app.config import settings


@pytest.mark.asyncio
async def test_gemini_model_not_found_uses_configured_fallback_model(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")
    monkeypatch.setattr(settings, "ai_fallback_models", "gemini-fallback-model")
    calls = []

    def handler(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model == "gemini-primary-model":
            return httpx.Response(404, request=request, json={
                "error": {"status": "NOT_FOUND", "message": "This model is no longer available to new users"}
            })
        return httpx.Response(200, request=request, json={"choices": [{"message": {"content": "ok"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await ai_provider._post_chat_completion(
            client, "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            headers={"Authorization": "Bearer test"}, payload={"model": "gemini-primary-model"},
        )
    assert response.status_code == 200
    assert calls == ["gemini-primary-model", "gemini-fallback-model"]


@pytest.mark.asyncio
async def test_retired_gemini_flash_lite_alias_is_replaced_by_current_free_fallback(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")
    monkeypatch.setattr(settings, "ai_fallback_models", "gemini-2.5-flash-lite")
    calls = []

    def handler(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model == "gemini-2.5-flash-lite":
            return httpx.Response(404, request=request, json={
                "error": {"status": "NOT_FOUND", "message": "This model is no longer available to new users"}
            })
        return httpx.Response(200, request=request, json={"choices": [{"message": {"content": "ok"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await ai_provider._post_chat_completion(
            client, "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            headers={"Authorization": "Bearer test"}, payload={"model": "gemini-2.5-flash-lite"},
        )
    assert response.status_code == 200
    assert calls == ["gemini-2.5-flash-lite", "gemini-3.5-flash-lite"]


@pytest.mark.asyncio
async def test_gemini_availability_uses_free_fallback_after_retired_primary(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", "test-gemini-key")
    monkeypatch.setattr(settings, "ai_model", "gemini-2.5-flash-lite")
    monkeypatch.setattr(settings, "ai_fallback_models", "gemini-2.5-flash-lite")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")
    calls = []

    def handler(request):
        model = request.url.path.rsplit("/", 1)[-1]
        calls.append(model)
        if model == "gemini-2.5-flash-lite":
            return httpx.Response(404, request=request, json={"error": {"status": "NOT_FOUND"}})
        return httpx.Response(200, request=request, json={
            "name": "models/gemini-3.5-flash-lite",
            "supportedGenerationMethods": ["generateContent"],
        })

    result = await ai_provider._check_provider_availability_uncached(transport=httpx.MockTransport(handler))
    assert result == {"status": "MODEL_CONFIGURED"}
    assert calls == ["gemini-2.5-flash-lite", "gemini-3.5-flash-lite"]


def test_gemini_model_not_found_detection_ignores_unrelated_route_404():
    response = httpx.Response(404, json={"error": {"status": "NOT_FOUND", "message": "route not found"}})
    assert ai_provider._is_gemini_model_not_found_response(response) is False
