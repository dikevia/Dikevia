from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_global_identity_tables_are_not_public_to_runtime_role():
    sql = (ROOT / "database/migrations/003_global_identity_rls.sql").read_text()
    assert "ALTER TABLE users ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE users FORCE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE platform_admins ENABLE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE platform_admins FORCE ROW LEVEL SECURITY" in sql
    assert "users_self_identity" in sql
    assert "platform_admins_self_read" in sql
    assert "platform_admins_bootstrap_insert" in sql
    assert "CREATE UNIQUE INDEX IF NOT EXISTS invitations_token_hash_uq" in sql


def test_identity_context_is_set_before_user_profile_read():
    main = (ROOT / "backend/app/main.py").read_text()
    auth_me = main.split('@app.get("/api/v1/auth/me")', 1)[1].split('@app.get("/api/v1/organizations")', 1)[0]
    assert auth_me.index("set_config('app.oidc_issuer'") < auth_me.index("SELECT id,email,display_name,status FROM users")
    assert auth_me.index("set_config('app.oidc_subject'") < auth_me.index("SELECT id,email,display_name,status FROM users")


def test_invitation_acceptance_sets_identity_context_before_user_upsert():
    main = (ROOT / "backend/app/main.py").read_text()
    accept = main.split('@app.post("/api/v1/invitations/accept"', 1)[1].split('@app.post("/api/v1/platform/organizations"', 1)[0]
    assert accept.index("set_config('app.oidc_issuer'") < accept.index("INSERT INTO users")
    assert accept.index("set_config('app.oidc_subject'") < accept.index("INSERT INTO users")
    assert "principal.email_verified" in accept


def test_platform_admin_check_sets_identity_context_before_registry_lookup():
    deps = (ROOT / "backend/app/dependencies.py").read_text()
    block = deps.split("async def require_platform_admin", 1)[1]
    assert block.index("set_config('app.oidc_issuer'") < block.index("JOIN platform_admins")
    assert block.index("set_config('app.oidc_subject'") < block.index("JOIN platform_admins")


def test_consolidated_schema_also_contains_global_identity_rls():
    sql = (ROOT / "database/schema.sql").read_text()
    assert "ALTER TABLE users FORCE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE platform_admins FORCE ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY users_self_identity" in sql
    assert "CREATE POLICY platform_admins_self_read" in sql


def test_platform_admin_bootstrap_sets_oidc_context_before_inserting_marker():
    sql = (ROOT / "database/bootstrap_platform_admin.sql").read_text()
    assert sql.index("set_config('app.oidc_issuer'") < sql.index("INSERT INTO users")
    assert sql.index("set_config('app.oidc_subject'") < sql.index("INSERT INTO users")
