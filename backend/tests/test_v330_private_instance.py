from app.config import Settings, validate_runtime_configuration
import pytest


def test_private_instance_requires_exactly_ten_seats():
    with pytest.raises(RuntimeError, match="égal à 10"):
        validate_runtime_configuration(Settings(private_instance_mode=True, private_instance_max_users=9))


def test_private_instance_rejects_stripe_secrets():
    with pytest.raises(RuntimeError, match="Stripe doit être entièrement désactivé"):
        validate_runtime_configuration(Settings(
            private_instance_mode=True,
            stripe_secret_key="sk_test_example",
            stripe_webhook_secret="whsec_example",
        ))


def test_private_instance_without_stripe_is_valid_in_development():
    validate_runtime_configuration(Settings(
        app_env="development",
        private_instance_mode=True,
        private_instance_max_users=10,
    ))


def test_private_mode_controls_are_present_in_api_and_frontend():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    main = (root / "backend/app/main.py").read_text(encoding="utf-8")
    frontend = (root / "frontend/index.html").read_text(encoding="utf-8")
    migration = (root / "database/migrations/015_private_instance_10_seats.sql").read_text(encoding="utf-8")
    assert "/api/v1/platform/private-members" in main
    assert "PENDING_APPROVAL" in main
    assert "window.PRIVATE_INSTANCE_MODE" in main
    assert "Approuver" in frontend
    assert "private_instance_set_member_status" in migration
    assert "active_count>=10" in migration


def test_private_migration_refuses_unsafe_existing_tenant_state():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    migration = (root / "database/migrations/015_private_instance_10_seats.sql").read_text(encoding="utf-8")
    assert "count(*) FROM organizations" in migration
    assert "count(*) FROM memberships WHERE status='ACTIVE'" in migration
    assert "at most one organization" in migration
    assert "at most ten active memberships" in migration
