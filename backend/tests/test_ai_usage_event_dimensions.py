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
