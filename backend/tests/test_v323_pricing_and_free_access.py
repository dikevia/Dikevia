from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_free_email_access_is_admin_managed_and_excluded_from_seat_count():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert '"/api/v1/platform/free-email-access"' in main
    assert "platform_free_email_access" in main
    assert "paid_active_users" in main
    migration = (ROOT / "database/migrations/010_subscription_catalog_and_free_email_access.sql").read_text(encoding="utf-8")
    assert "tenant_billing_seat_counts" in migration
    assert "SET row_security = off" in migration
    assert "Les adresses bénéficiant d'un accès gratuit ne consomment pas de place" in main

def test_migration_has_reversible_legacy_plan_preservation():
    up = (ROOT / "database/migrations/010_subscription_catalog_and_free_email_access.sql").read_text(encoding="utf-8")
    down = (ROOT / "database/migrations/rollback/010_subscription_catalog_and_free_email_access.down.sql").read_text(encoding="utf-8")
    assert "LEGACY_ESSENTIAL_3" in up and "LEGACY_SYNDICAT_10" in up
    assert "platform_free_email_access" in up and "platform_audit_events" in up
    assert "LEGACY_ESSENTIAL_3" in down and "LEGACY_SYNDICAT_10" in down

def test_checkout_stays_disabled_until_credit_enforcement_is_implemented():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert '"billing_enabled": False' in main
    assert "compteur de crédits mensuels" in main
    assert '"line_items[0][price_data][tax_behavior]"' not in main
