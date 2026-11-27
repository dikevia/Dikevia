from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_all_settings_variables_are_documented_in_env_example():
    module = load_script("audit_env_example", ROOT / "scripts" / "audit_env_example.py")
    assert module.missing_keys() == set()


def test_asyncpg_is_declared_as_runtime_dependency():
    requirements = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    dev_requirements = (ROOT / "backend" / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "asyncpg>=" in requirements
    assert "pytest>=" in dev_requirements
    assert "pytest>=" not in requirements


def test_migration_runner_protects_baseline_and_requires_down_migration():
    module = load_script("db_migrate", ROOT / "scripts" / "db_migrate.py")
    migration = ROOT / "database" / "migrations" / "009_permanent_legal_knowledge.sql"
    assert module.down_path(migration).name == "009_permanent_legal_knowledge.down.sql"
    assert module.down_path(migration).is_file()
    assert module.BASELINE_VERSION == 9
    assert module.strip_transaction_wrappers("BEGIN;\nSELECT 1;\nCOMMIT;").strip() == "SELECT 1;"
    migration_sql = migration.read_text(encoding="utf-8")
    stripped = module.strip_transaction_wrappers(migration_sql)
    assert not any(line.strip().upper() in {"BEGIN;", "COMMIT;"} for line in stripped.splitlines())


def test_production_preflight_requires_auth0_and_not_keycloak(tmp_path):
    module = load_script("audit_production_env", ROOT / "scripts" / "audit_production_env.py")
    env = tmp_path / "production.env"
    env.write_text("\n".join([
        "APP_ENV=production",
        "DEBUG=false",
        "POSTGRES_MIGRATION_PASSWORD=migration-secret-unique-000000000001",
        "POSTGRES_APP_PASSWORD=application-secret-unique-0000000002",
        "POSTGRES_INGEST_PASSWORD=ingestion-secret-unique-00000000003",
        "POSTGRES_MONITOR_PASSWORD=monitor-secret-unique-000000000004",
        "DATABASE_URL=postgresql://cfdt_juris_app:application-secret-unique-0000000002@db/cfdt_juris",
        "LEGAL_CORPUS_INGEST_DATABASE_URL=postgresql://cfdt_juris_ingest:ingestion-secret-unique-00000000003@db/cfdt_juris",
        "PUBLIC_APP_URL=https://juris.example.org",
        "OIDC_PROVIDER=auth0",
        "OIDC_ISSUER=https://tenant.example.auth0.com/",
        "OIDC_JWKS_URL=https://tenant.example.auth0.com/.well-known/jwks.json",
        "OIDC_CLIENT_ID=auth0-client-id",
        "OIDC_AUDIENCE=https://api.example.org",
        "OIDC_AUTHORIZATION_AUDIENCE=https://api.example.org",
        "OIDC_IDENTITY_COMPAT_ISSUER=https://legacy-identity.example.org/realms/cfdt",
        "OIDC_IDENTITY_SUBJECT_PREFIX=auth0|",
        "OIDC_ALGORITHMS=RS256",
        "CORS_ORIGINS=https://juris.example.org",
        "BACKUP_AGE_RECIPIENT=age1qexamplepublickey",
    ]), encoding="utf-8")
    assert module.audit(env) == []


def test_staging_configuration_is_separate_and_uses_sandbox_piste():
    env = (ROOT / "deploy" / ".env.staging.example").read_text(encoding="utf-8")
    assert "JURIS_RUNTIME_ENV_FILE=../.env.staging.runtime" in env
    assert "API_PORT=18000" in env
    assert "OIDC_PROVIDER=auth0" in env
    assert "OIDC_PROVIDER=keycloak" not in env
    assert "LEGIFRANCE_ENVIRONMENT=sandbox" in env
    assert "APP_ENV=production" in env
    assert "https://juris-staging.example.org" in env


def test_default_compose_stack_does_not_start_or_require_keycloak():
    compose = (ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")
    assert compose.count('profiles: ["legacy-keycloak"]') == 2
    api = compose.split("  api:", 1)[1].split("  migrator:", 1)[0]
    dependencies = api.split("depends_on:", 1)[1].split("healthcheck:", 1)[0]
    assert "keycloak" not in dependencies.lower()


def test_monitoring_configuration_contains_api_and_database_probes_only():
    compose = (ROOT / "deploy" / "docker-compose.monitoring.yml").read_text(encoding="utf-8")
    prometheus = (ROOT / "deploy" / "monitoring" / "prometheus.yml").read_text(encoding="utf-8")
    alerts = (ROOT / "deploy" / "monitoring" / "alerts.yml").read_text(encoding="utf-8")
    assert "postgres-exporter" in compose
    assert "http://api:8000/ready" in prometheus
    assert "keycloak" not in prometheus.lower()
    assert "JurisKeycloakReadinessDown" not in alerts
    assert "JurisPostgresDown" in alerts
    assert (ROOT / "deploy/monitoring/juris-overview.json").is_file()


def test_runtime_env_renderer_excludes_infrastructure_admin_secrets(tmp_path):
    module = load_script("render_runtime_env", ROOT / "scripts" / "render_runtime_env.py")
    source = tmp_path / ".env.source"
    output = tmp_path / ".env.runtime"
    source.write_text(
        "DATABASE_URL=postgresql://cfdt_juris_app:app@db/cfdt_juris\n"
        "LEGAL_CORPUS_INGEST_DATABASE_URL=postgresql://cfdt_juris_ingest:ingest@db/cfdt_juris\n"
        "POSTGRES_MIGRATION_PASSWORD=never-copy-this\n"
        "KEYCLOAK_DB_PASSWORD=never-copy-this-either\n",
        encoding="utf-8",
    )
    values = module.parse_assignments(source)
    allowed = module.settings_keys()
    output.write_text("\n".join(f"{k}={values[k]}" for k in sorted(allowed) if k in values), encoding="utf-8")
    rendered = output.read_text(encoding="utf-8")
    assert "DATABASE_URL=" in rendered
    assert "LEGAL_CORPUS_INGEST_DATABASE_URL=" in rendered
    assert "POSTGRES_MIGRATION_PASSWORD" not in rendered
    assert "KEYCLOAK_DB_PASSWORD" not in rendered


def test_env_upgrade_uses_same_new_ingest_secret_for_password_and_connection_url():
    module = load_script("upgrade_env_file", ROOT / "scripts" / "upgrade_env_file.py")
    content = "APP_ENV=development\n"
    defaults = {
        "POSTGRES_INGEST_PASSWORD": "CHANGE_ME_INGEST",
        "LEGAL_CORPUS_INGEST_DATABASE_URL": "postgresql://cfdt_juris_ingest:CHANGE_ME_INGEST@db/cfdt_juris",
    }
    merged, added = module.merge_env_content(content, {}, defaults)
    assert added == 2
    password = next(line.split("=", 1)[1] for line in merged.splitlines() if line.startswith("POSTGRES_INGEST_PASSWORD="))
    url = next(line.split("=", 1)[1] for line in merged.splitlines() if line.startswith("LEGAL_CORPUS_INGEST_DATABASE_URL="))
    assert f"cfdt_juris_ingest:{password}@" in url


def test_env_upgrade_refuses_mismatched_database_role_passwords():
    module = load_script("upgrade_env_file", ROOT / "scripts" / "upgrade_env_file.py")
    content = (
        "POSTGRES_APP_PASSWORD=right-secret\n"
        "DATABASE_URL=postgresql://cfdt_juris_app:wrong-secret@db/cfdt_juris\n"
    )
    import pytest
    with pytest.raises(SystemExit, match="Incohérence"):
        module.validate_database_passwords(content)
