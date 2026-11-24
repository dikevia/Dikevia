from pathlib import Path
from types import SimpleNamespace

from app import main


ROOT = Path(__file__).resolve().parents[1]


def test_ai_provider_label_uses_exact_gemini_endpoint_without_logging_credentials(monkeypatch):
    monkeypatch.setattr(main, "settings", SimpleNamespace(
        ai_api_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        ai_api_key="synthetic-test-key",
        ai_model="gemini-2.5-flash",
    ))
    assert main._configured_ai_provider() == "gemini"


def test_ai_provider_label_keeps_other_openai_compatible_endpoints_distinct(monkeypatch):
    monkeypatch.setattr(main, "settings", SimpleNamespace(
        ai_api_base_url="https://api.example.test/v1",
        ai_api_key="synthetic-test-key",
        ai_model="model-test",
    ))
    assert main._configured_ai_provider() == "openai_compatible"


def test_ai_provider_label_marks_missing_configuration(monkeypatch):
    monkeypatch.setattr(main, "settings", SimpleNamespace(
        ai_api_base_url="",
        ai_api_key="",
        ai_model="",
    ))
    assert main._configured_ai_provider() == "not_configured"


def test_local_document_ai_usage_records_provider_operation_and_latency_on_success_and_failure():
    source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    start = source.index('@app.post("/api/v1/legal/compliance/review/{document_id}")')
    end = source.index('@app.get("/api/v1/platform/legal-corpus/freshness")', start)
    route = source[start:end]

    assert 'answer_started_at = time.perf_counter()' in route
    assert '"provider": _configured_ai_provider()' in route
    assert '"operation": "answer_generation"' in route
    assert route.count('"latency_ms": max(0, round((time.perf_counter() - answer_started_at) * 1000))') == 2
    assert '"provider": "openai_compatible"' not in route
    assert 'type(exc).__name__' in route
