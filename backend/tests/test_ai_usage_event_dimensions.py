import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "migrations" / "027_ai_usage_event_dimensions.sql"


def test_ai_usage_events_allow_multiple_operations_per_request():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "DROP CONSTRAINT ai_usage_events_pkey" in sql
    assert "PRIMARY KEY (event_id)" in sql
    assert "operation varchar(40) NOT NULL DEFAULT 'answer_generation'" in sql
    assert "latency_ms integer" in sql
    assert "ON ai_usage_events(request_id, created_at, event_id)" in sql
    assert "GRANT USAGE, SELECT ON SEQUENCE ai_usage_events_event_id_seq TO cfdt_juris_app" in sql


def test_database_outcome_constraint_accepts_completed_provider_operations():
    sql = MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"CHECK\s*\(\s*outcome\s+IN\s*\((.*?)\)\s*\)", sql, re.I | re.S)
    assert match
    allowed = set(re.findall(r"'([A-Z][A-Z0-9_]*)'", match.group(1)))
    assert "COMPLETED" in allowed
    assert "PROVIDER_ERROR" in allowed


def test_per_operation_telemetry_does_not_expose_payload_content():
    schema = (ROOT / "backend" / "app" / "schemas.py").read_text(encoding="utf-8")
    main = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert "ai_usage_events: list[dict] = Field(default_factory=list, exclude=True)" in schema
    assert "usage.get(\"operation\", \"answer_generation\")" in main
    assert "for usage_event in usage_events:" in main
    assert 'usage["prompt"]' not in main
    assert 'usage["response"]' not in main



def test_provider_usage_event_records_known_tokens_and_latency(monkeypatch):
    from app import ai_provider

    events = []
    monkeypatch.setattr(ai_provider.time, "perf_counter", lambda: 102.5)
    monkeypatch.setattr(
        ai_provider.settings,
        "ai_api_base_url",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    )
    monkeypatch.setattr(ai_provider.settings, "ai_model", "configured-model")

    ai_provider._record_provider_usage_event(
        events,
        "research_planning",
        100.0,
        {
            "model": "actual-model",
            "usage": {"prompt_tokens": 8, "completion_tokens": 3},
        },
    )

    assert events == [{
        "operation": "research_planning",
        "provider": "gemini",
        "model": "actual-model",
        "prompt_tokens": 8,
        "completion_tokens": 3,
        "total_tokens": 11,
        "latency_ms": 2500,
        "outcome": "COMPLETED",
    }]


def test_provider_error_usage_event_keeps_unknown_tokens_null(monkeypatch):
    from app import ai_provider

    events = []
    monkeypatch.setattr(ai_provider.time, "perf_counter", lambda: 101.0)
    monkeypatch.setattr(ai_provider.settings, "ai_api_base_url", "https://api.example.test/v1")
    monkeypatch.setattr(ai_provider.settings, "ai_model", "configured-model")

    ai_provider._record_provider_usage_event(
        events, "claim_entailment", 100.0, None, "PROVIDER_ERROR"
    )

    assert len(events) == 1
    assert events[0]["provider"] == "openai_compatible"
    assert events[0]["model"] == "configured-model"
    assert events[0]["prompt_tokens"] is None
    assert events[0]["completion_tokens"] is None
    assert events[0]["total_tokens"] is None
    assert events[0]["latency_ms"] == 1000
    assert events[0]["outcome"] == "PROVIDER_ERROR"



def test_entailment_provider_failure_does_not_overwrite_successful_answer_usage():
    source = (ROOT / "backend" / "app" / "orchestrator.py").read_text(encoding="utf-8")
    assert "if ai_usage is None and settings.ai_api_base_url and settings.ai_model:" in source
    assert "Do not overwrite it." in source
