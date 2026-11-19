from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_account_trial_starts_once_after_verified_oidc_sign_in():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    dependencies = (ROOT / "backend/app/dependencies.py").read_text(encoding="utf-8")
    assert "principal.email_verified and principal.email" in main
    assert "trial_started_at=COALESCE(trial_started_at,now())" in main
    assert "trial_expires_at=COALESCE(trial_expires_at,COALESCE(trial_started_at,now())+interval '72 hours')" in main
    assert "if not principal.email_verified or not principal.email" in dependencies
    migration = (ROOT / "database/migrations/020_account_trial_founder_entitlements.sql").read_text(encoding="utf-8")
    assert "trial_email_claims" in migration
    assert "pg_advisory_xact_lock(33010341)" in migration
    assert "claim_trial_email" in dependencies and "TRIAL_ALREADY_USED" in dependencies


def test_expired_trial_is_blocked_server_side_but_billing_and_identity_remain_available():
    dependencies = (ROOT / "backend/app/dependencies.py").read_text(encoding="utf-8")
    assert '"/api/v1/billing/checkout"' in dependencies
    assert '"/api/v1/billing/portal"' in dependencies
    assert '"/api/v1/access/status"' in dependencies
    assert 'raise HTTPException(402' in dependencies
    assert '"TRIAL_EXPIRED"' in dependencies
    assert "Vos données sont conservées" in dependencies


def test_founder_entitlements_are_individual_and_limited_to_ten_atomic_slots():
    migration = (ROOT / "database/migrations/020_account_trial_founder_entitlements.sql").read_text(encoding="utf-8")
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert "slot_number BETWEEN 1 AND 10" in migration
    assert "pg_advisory_xact_lock(33010340)" in migration
    assert "founder_entitlements_one_active_per_slot_idx" in migration
    assert "founder_entitlements_one_active_per_user_idx" in migration
    assert "platform_admin_grant_founder_entitlement" in migration
    assert "platform_admin_list_founder_entitlements" in migration
    assert "La place 1 est réservée au propriétaire fondateur" in main
    assert "founder_entitlements" in (ROOT / "backend/app/dependencies.py").read_text(encoding="utf-8")


def test_trial_and_founder_entitlement_are_not_organization_seat_limits():
    migration = (ROOT / "database/migrations/020_account_trial_founder_entitlements.sql").read_text(encoding="utf-8")
    assert "organization_id" not in migration
    assert "founder_entitlements" in migration
    assert "72 hours" in migration


def test_trial_and_founder_migration_has_rollback():
    assert (ROOT / "database/migrations/rollback/020_account_trial_founder_entitlements.down.sql").is_file()

def test_legacy_complimentary_email_allowlist_does_not_override_trial_expiry():
    dependencies = (ROOT / "backend/app/dependencies.py").read_text(encoding="utf-8")
    assert "platform_free_email_access" not in dependencies
    assert "SUBSCRIPTION_REQUIRED" in dependencies
    assert "TRIAL_EXPIRED" in dependencies


def test_platform_founder_admin_operations_require_verified_oidc_email():
    dependencies = (ROOT / "backend/app/dependencies.py").read_text(encoding="utf-8")
    assert "Une adresse e-mail vérifiée est requise pour les opérations administrateur" in dependencies

def test_owner_founder_slot_is_reserved_and_requires_verified_configured_identity():
    config = (ROOT / "backend/app/config.py").read_text(encoding="utf-8")
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    env = (ROOT / "deploy/.env.example").read_text(encoding="utf-8")
    assert "founder_owner_email: str = \"\"" in config
    assert "FOUNDER_OWNER_EMAIL" in config and "FOUNDER_OWNER_EMAIL=" in env
    assert '"/api/v1/platform/founder-entitlements/owner"' in main
    assert "La place 1 est réservée au propriétaire fondateur" in main

def test_frontend_displays_trial_countdown_and_routes_expired_users_to_billing():
    frontend = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'id="trialBanner"' in frontend
    assert "Essai gratuit actif" in frontend
    assert "loadAccessStatus" in frontend
    assert "setView('billing')" in frontend
    assert "14,90" in frontend and "29,00" in frontend
