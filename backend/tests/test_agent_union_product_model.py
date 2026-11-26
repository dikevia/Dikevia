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
    assert "consume_daily_chat_question(" in source
    quota_source = inspect.getsource(__import__("app.rate_limit", fromlist=["consume_daily_chat_question"]).consume_daily_chat_question)
    assert "question_count < $2" in quota_source
    assert "Europe/Paris" in quota_source
    assert "limite de 5 questions" in source


def test_syndicate_only_endpoints_have_server_side_subscription_dependency():
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
    migration = (ROOT / "database/migrations/030_chat_daily_question_quota.sql").read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_user_id" in migration
    assert "question_count BETWEEN 1 AND 5" in migration
    assert "GRANT DELETE ON chat_daily_question_usage" not in migration


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
    assert "prepare_instance_with_legal_sources" in source

def test_standalone_legal_documents_and_organization_management_are_union_only():
    source = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    guarded_paths = (
        "/api/v1/legal/legifrance/search",
        "/api/v1/legal/jurisprudence/administrative/search",
        "/api/v1/legal/knowledge/search",
        "/api/v1/legal/cgfp/search",
        "/api/v1/documents/search",
        "/api/v1/collectivities",
        "/api/v1/organizations/me/invitations",
    )
    for path in guarded_paths:
        route_index = source.index(path)
        decorator_start = source.rfind("@app.", 0, route_index)
        decorator_end = source.find("\n", route_index)
        decorator = source[decorator_start:decorator_end]
        assert "require_syndicate_subscription" in decorator, path

def test_frontend_exposes_instances_only_to_union_entitlements_and_removes_old_pricing():
    frontend = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'data-view="instances" data-premium' in frontend
    assert "hasSyndicateTools=Boolean(sub.features?.syndicate_tools||sub.premium_access)" in frontend
    assert "AGENT_5_QUESTIONS" in frontend
    assert "SYNDICAT_5_ACCES" in frontend
    assert "SYNDICAT_10_ACCES" in frontend
    assert "SYNDICAT_15_ACCES" in frontend
    assert "125 crédits par mois" not in frontend
    assert "Essentiel · 1 accès" not in frontend
    assert "Collectivité & Syndicats · 15 accès" not in frontend
    assert "Préparation des instances" in frontend
