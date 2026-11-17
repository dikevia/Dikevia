from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_commercial_routes_are_platform_admin_and_tenant_scoped():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert '"/api/v1/platform/commercial/summary"' in main
    assert '"/api/v1/platform/commercial/invoices"' in main
    assert '"/api/v1/platform/commercial/organizations"' in main
    assert '"/api/v1/billing/invoices"' in main
    assert "platform=Depends(require_platform_admin)" in main
    assert "ctx: TenantContext = Depends(get_tenant_context)" in main


def test_invoice_webhook_persists_only_after_signature_and_is_idempotent():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert "verify_stripe_signature(raw, signature, settings.stripe_webhook_secret)" in main
    assert "app.stripe_webhook_verified" in main
    assert "ON CONFLICT(stripe_invoice_id) DO UPDATE" in main
    assert "platform_lookup_org_by_stripe_subscription" in main
    assert "platform_lookup_plan_by_stripe_subscription" in main


def test_commercial_migration_has_rls_and_admin_guards_and_rollback():
    up = (ROOT / "database/migrations/011_commercial_customer_console.sql").read_text(encoding="utf-8")
    down = (ROOT / "database/migrations/rollback/011_commercial_customer_console.down.sql").read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in up and "FORCE ROW LEVEL SECURITY" in up
    assert "stripe_invoice_webhook_insert" in up and "stripe_invoice_webhook_update" in up
    assert "IS DISTINCT FROM 'verified'" in up
    assert "platform_admin_commercial_summary" in up
    assert "tenant_billing_invoice_history" in up
    assert "DROP TABLE IF EXISTS stripe_invoice_records" in down


def test_frontend_exposes_platform_commercial_dashboard_and_customer_invoices():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    for item in ("commercialMetrics", "commercialOrganizations", "commercialInvoices", "tenantInvoices",
                 "CA encaissé du mois", "Historique des factures"):
        assert item in html
