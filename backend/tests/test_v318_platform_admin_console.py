from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_platform_admin_routes_are_protected_and_present():
    source = (ROOT / "backend/app/main.py").read_text()
    assert '@app.get("/api/v1/platform/organizations")' in source
    assert '@app.patch("/api/v1/platform/organizations/{organization_id}/status")' in source
    assert 'Depends(require_platform_admin)' in source
    assert 'platform_admin_list_organizations' in source
    assert 'platform_admin_set_organization_status' in source


def test_platform_functions_recheck_admin_and_are_not_public():
    migration = (ROOT / "database/migrations/008_platform_admin_console.sql").read_text()
    assert migration.count("LANGUAGE plpgsql\nSECURITY DEFINER") == 2
    assert migration.count("platform_admins WHERE user_id = p_user_id") == 2
    assert "SET row_security = off" in migration
    assert "REVOKE ALL ON FUNCTION" in migration
    assert "GRANT EXECUTE ON FUNCTION" in migration


def test_platform_admin_functions_are_only_granted_to_dedicated_role():
    migration = (ROOT / "database/migrations/016_platform_admin_database_role.sql").read_text()
    assert "REVOKE EXECUTE ON FUNCTION private_instance_pending_members(uuid) FROM cfdt_juris_app" in migration
    assert "GRANT EXECUTE ON FUNCTION private_instance_pending_members(uuid) TO cfdt_juris_platform_admin" in migration
    assert "REVOKE INSERT, UPDATE ON platform_free_email_access FROM cfdt_juris_app" in migration
    source = (ROOT / "backend/app/main.py").read_text()
    assert "get_platform_admin_pool()" in source
    assert "PLATFORM_ADMIN_DATABASE_URL" in (ROOT / "backend/app/config.py").read_text()


def test_platform_console_is_not_shown_by_default_and_has_explicit_actions():
    frontend = (ROOT / "frontend/index.html").read_text()
    assert 'id="platformScreen" class="hidden"' in frontend
    assert "data-free=" in frontend
    assert "data-status=" in frontend
    assert "platformCreateForm" in frontend
