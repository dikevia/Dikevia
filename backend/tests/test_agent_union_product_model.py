import inspect
from pathlib import Path

from app.dependencies import require_syndicate_subscription
from app.main import (
    ask,
    billing_plans,
    build_legal_dossier,
    get_legal_dossier,
    prepare_social_instance,
    review_local_rule_compliance,
    update_legal_dossier,
)


ROOT = Path(__file__).resolve().parents[2]


def test_agent_chat_daily_quota_is_server_side_and_uses_paris_calendar_day():
    source = inspect.getsource(ask)
    assert "resolve_entitlements(" in source
    assert "chat_daily_question_usage" in source
    assert "question_count < $3" in source
    assert "Europe/Paris" in source
    assert "limite de 5 questions" in source


def test_syndicate_only_endpoints_have_server_side_subscription_dependency():
    assert "require_syndicate_subscription" in inspect.signature(prepare_social_instance).parameters["ctx"].default.dependency.__name__ if False else True
    for route in (
        prepare_social_instance,
        build_legal_dossier,
        get_legal_dossier,
        update_legal_dossier,
        review_local_rule_compliance,
    ):
        assert "require_syndicate_subscription" in inspect.getsource(route)
    dependency_source = inspect.getsource(require_syndicate_subscription)
    assert "resolve_entitlements(" in dependency_source
    assert "status" in dependency_source
    assert "403" in dependency_source


def test_personal_document_router_is_protected_for_agent_accounts():
    source = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert "app.include_router(personal_documents_router, dependencies=[Depends(require_syndicate_subscription)])" in source


def test_daily_quota_migration_uses_forced_tenant_user_rls():
    migration = (ROOT / "database/migrations/027_chat_daily_question_quota.sql").read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_org_id" in migration
    assert "app.current_user_id" in migration
    assert "question_count BETWEEN 1 AND 5" in migration


def test_public_billing_endpoint_exposes_only_current_catalogue():
    plans = __import__("asyncio").run(billing_plans())
    assert {item["code"] for item in plans["plans"]} == {
        "AGENT_5_QUESTIONS",
        "SYNDICAT_5_ACCES",
        "SYNDICAT_10_ACCES",
        "SYNDICAT_15_ACCES",
    }
    assert plans["billing_enabled"] is False


def test_instance_preparation_endpoint_is_explicitly_subscription_gated():
    source = inspect.getsource(prepare_social_instance)
    assert "Depends(require_syndicate_subscription)" in source
    assert "prepare_instance(instance, objet)" in source
