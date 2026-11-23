from pathlib import Path
import inspect

from app import main


ROOT = Path(__file__).resolve().parents[2]


def test_credit_wallet_is_rls_scoped_and_runtime_can_only_debit():
    sql = (ROOT / "database/migrations/025_credit_wallet_foundation.sql").read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON credit_accounts, credit_ledger_entries FROM cfdt_juris_app" in sql
    assert "GRANT EXECUTE ON FUNCTION wallet_apply_entry" in sql
    assert "TO cfdt_juris_app" in sql
    assert "GRANT EXECUTE ON FUNCTION wallet_admin_grant_entry" in sql
    assert "TO cfdt_juris_platform_admin" in sql
    assert "p_delta >= 0" in sql


def test_founder_entitlement_requires_an_active_verified_oidc_user_and_platform_admin():
    sql = (ROOT / "database/migrations/026_platform_founder_entitlements.sql").read_text(encoding="utf-8")
    assert "UNIQUE (oidc_issuer, oidc_subject)" in sql
    assert "WHERE id=p_target_user_id AND status='ACTIVE'" in sql
    assert "platform_admins WHERE user_id=p_actor_user_id" in sql
    assert "REVOKE EXECUTE ON FUNCTION platform_admin_grant_founder_entitlement" in sql
    assert "TO cfdt_juris_platform_admin" in sql
    assert "email_normalized" not in sql
    assert "email text" not in sql.lower()


def test_founder_api_uses_internal_user_id_and_is_auditable():
    grant = inspect.getsource(main.platform_grant_founder_entitlement)
    revoke = inspect.getsource(main.platform_revoke_founder_entitlement)
    identity = inspect.getsource(main.account_identity)
    subscription = inspect.getsource(main.billing_subscription)
    assert "user_id" in grant and "platform_admin_grant_founder_entitlement" in grant
    assert "email" not in grant.lower()
    assert "platform_admin_revoke_founder_entitlement" in revoke
    assert "platform_founder_entitlements" in subscription
    assert "oidc_identity_verified" in identity
    assert "email" not in identity.lower()


def test_platform_admin_ui_separates_founder_entitlement_from_chat():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'id="platformScreen"' in html
    assert 'id="founderEntitlementPanel"' in html
    assert 'id="founderEntitlementForm"' in html
    assert "/api/v1/platform/founder-entitlements" in html
    assert 'id="accountUserId"' in html
