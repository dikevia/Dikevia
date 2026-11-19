from pathlib import Path


def test_ai_usage_outcome_migration_accepts_security_orchestrator_statuses():
    migration = (
        Path(__file__).resolve().parents[2]
        / "database/migrations/020_ai_usage_outcome_compatibility.sql"
    ).read_text(encoding="utf-8")

    for outcome in (
        "ANSWERED",
        "REJECTED_UNGROUNDED",
        "PROVIDER_ERROR",
        "REJECTED_UNSUPPORTED_CLAIMS",
        "ABSTAINED_NO_SUPPORTED_CLAIMS",
        "REJECTED_UNSUPPORTED_ENTAILMENT",
        "ANSWERED_WITH_VERIFIED_QUOTES_AND_ENTAILMENT_CHECK",
        "REJECTED_AMBIGUOUS_SOURCE",
    ):
        assert f"'{outcome}'" in migration
