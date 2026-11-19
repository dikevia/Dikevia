from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_credit_wallet_is_tenant_scoped_append_only_and_idempotent():
    migration = (ROOT / "database/migrations/021_credit_wallet_foundation.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE credit_accounts" in migration
    assert "CREATE TABLE credit_ledger_entries" in migration
    assert "UNIQUE (organization_id, idempotency_key)" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "FOR SELECT USING" in migration
    assert "wallet_apply_entry" in migration
    assert "wallet_admin_grant_entry" in migration
    assert "p_entry_type IS DISTINCT FROM 'USAGE_DEBIT'" in migration
    assert "GRANT EXECUTE ON FUNCTION wallet_admin_grant_entry" in migration
    assert "FOR UPDATE" in migration
    assert "v_balance + p_delta < 0" in migration
    assert "ON CONFLICT(organization_id) DO NOTHING" in migration
    assert "No monthly grants, purchases or AI debits are activated" in migration


def test_wallet_debit_is_not_connected_to_production_chat_yet():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert "wallet_apply_entry" not in main
    assert "record_ai_usage_event" in main


def test_founder_entitlement_is_bound_to_verified_oidc_identity_not_email():
    migration = (ROOT / "database/migrations/022_platform_founder_entitlements.sql").read_text(encoding="utf-8")
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert "UNIQUE (oidc_issuer, oidc_subject)" in migration
    assert "FROM users WHERE id=p_target_user_id AND status='ACTIVE'" in migration
    assert "platform_admin_grant_founder_entitlement" in migration
    assert "platform_admin_revoke_founder_entitlement" in migration
    assert "platform_admin_list_founder_entitlements" in migration
    assert "REVOKE SELECT ON platform_founder_entitlements FROM cfdt_juris_platform_admin" in migration
    assert "platform_founder_self_read" in migration
    assert "/api/v1/platform/founder-entitlements" in main
    assert 'platform_admin_grant_founder_entitlement($1::uuid,$2::uuid,$3)' in main
    assert '/api/v1/account/identity' in main
    assert "founder_entitlement" in main
    assert "email_normalized" not in migration
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'id="founderEntitlementForm"' in html
    assert 'id="founderEntitlementsBody"' in html
    assert "loadFounderEntitlements()" in html
    assert "Identifiant de compte vérifié" in html
    assert "Accès fondateur permanent — fonctionnalités premium" in html


def test_founder_entitlement_requires_the_target_identity_to_have_logged_in():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert "Ce compte n'a pas encore été vérifié par une connexion OIDC" in main
    assert "oidc_subject" not in main[main.index("async def platform_grant_founder_entitlement"):main.index("@app.delete(\"/api/v1/platform/founder-entitlements") ]


def test_ai_outcome_migration_widens_column_for_long_verified_status():
    migration = (ROOT / "database/migrations/020_ai_usage_outcome_compatibility.sql").read_text(encoding="utf-8")
    rollback = (ROOT / "database/migrations/rollback/020_ai_usage_outcome_compatibility.down.sql").read_text(encoding="utf-8")
    assert "ALTER COLUMN outcome TYPE varchar(80)" in migration
    assert "ANSWERED_WITH_VERIFIED_QUOTES_AND_ENTAILMENT_CHECK" in migration
    assert "length(outcome)>40" in rollback
    assert "ALTER COLUMN outcome TYPE varchar(40)" in rollback


def test_wallet_and_founder_migrations_have_rollback_scripts():
    rollback = ROOT / "database/migrations/rollback"
    assert (rollback / "020_ai_usage_outcome_compatibility.down.sql").exists()
    assert (rollback / "021_credit_wallet_foundation.down.sql").exists()
    assert (rollback / "022_platform_founder_entitlements.down.sql").exists()
