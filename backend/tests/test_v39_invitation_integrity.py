from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pending_invitation_is_unique_per_org_and_email():
    migration = (ROOT / "database/migrations/006_invitation_integrity.sql").read_text()
    schema = (ROOT / "database/schema.sql").read_text()
    main = (ROOT / "backend/app/main.py").read_text()
    assert "PARTITION BY organization_id, lower(email_normalized)" in migration
    assert "invitations_one_pending_per_email_uq" in migration
    assert "ON CONFLICT (organization_id,(lower(email_normalized))) WHERE status='PENDING' DO NOTHING" in main
    assert "Une invitation est déjà en attente" in main
    assert "invitations_one_pending_per_email_uq" in schema


def test_acceptance_cannot_overwrite_existing_active_membership_role():
    main = (ROOT / "backend/app/main.py").read_text()
    assert 'SELECT status FROM memberships' in main
    assert 'existing_membership["status"] == "ACTIVE"' in main
    assert "L'invitation ne peut pas modifier son rôle" in main
    assert "pg_advisory_xact_lock(hashtextextended" in main


def test_production_keycloak_admin_endpoint_requires_https_origin_only():
    config = (ROOT / "backend/app/config.py").read_text()
    assert "KEYCLOAK_ADMIN_BASE_URL doit utiliser HTTPS en production" in config
    assert "doit être une origine sans chemin" in config
