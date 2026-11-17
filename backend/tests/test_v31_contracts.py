from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_platform_admin_is_separate_from_tenant_roles():
    sql = (ROOT / "database/migrations/001_initial_multi_tenant.sql").read_text()
    grants = (ROOT / "database/grant_runtime_permissions.sql").read_text()
    deps = (ROOT / "backend/app/dependencies.py").read_text()
    assert "CREATE TABLE platform_admins" in sql
    assert "JOIN platform_admins pa" in deps
    assert "GRANT SELECT ON platform_admins" in grants
    assert "INSERT ON platform_admins" not in grants
    assert "ORG_ADMIN','LEGAL_EDITOR','MEMBER" in sql


def test_invitation_token_lookup_is_narrow_and_tenant_write_still_scoped():
    sql = (ROOT / "database/migrations/002_v31_invitations.sql").read_text()
    assert "token_hash=NULLIF(current_setting('app.invitation_token_hash',true),'')" in sql
    assert "WITH CHECK(organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid)" in sql


def test_invitation_acceptance_binds_verified_oidc_email_and_is_single_use():
    main = (ROOT / "backend/app/main.py").read_text()
    security = (ROOT / "backend/app/security.py").read_text()
    assert "principal.email_verified" in main
    assert "invitation[\"status\"] != \"PENDING\"" in main
    assert "SET status='ACCEPTED'" in main
    assert "INVITATION_REVOKED" in main
    assert "Cache-Control" in main
    assert "email_verified" in security


def test_platform_org_creation_has_dedicated_dependency():
    main = (ROOT / "backend/app/main.py").read_text()
    assert '"/api/v1/platform/organizations"' in main
    assert "Depends(require_platform_admin)" in main


def test_invitation_schema_cannot_assign_platform_admin_role():
    schemas = (ROOT / "backend/app/schemas.py").read_text()
    assert 'Literal["ORG_ADMIN", "LEGAL_EDITOR", "MEMBER"]' in schemas
    assert "PLATFORM_ADMIN" not in schemas
