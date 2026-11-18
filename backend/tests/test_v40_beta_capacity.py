from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_beta_user_cap_defaults_to_three_and_is_configurable():
    config = (ROOT / "backend/app/config.py").read_text()
    render = (ROOT / "render.yaml").read_text()
    env = (ROOT / "deploy/.env.example").read_text()
    assert "beta_max_users: int = 3" in config
    assert "BETA_MAX_USERS" in config
    assert '      - key: BETA_MAX_USERS\n        value: "3"' in render
    assert "BETA_MAX_USERS=3" in env


def test_beta_user_cap_is_enforced_for_invites_and_acceptance():
    main = (ROOT / "backend/app/main.py").read_text()
    assert main.count("beta_user_slot_available($1,$2)") >= 2
    assert "Limite temporaire de" in main


def test_beta_capacity_counts_active_users_pending_invites_and_platform_admins():
    migration = (ROOT / "database/migrations/019_temporary_beta_user_cap.sql").read_text()
    assert "pg_advisory_xact_lock(33010331)" in migration
    assert "FROM memberships m" in migration
    assert "FROM invitations i" in migration
    assert "FROM platform_admins pa" in migration
    assert "GRANT EXECUTE ON FUNCTION beta_user_slot_available(text,integer) TO cfdt_juris_app" in migration
