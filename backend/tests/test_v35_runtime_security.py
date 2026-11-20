import pytest
from app.config import Settings, validate_runtime_configuration
from app.security import MAX_BEARER_TOKEN_LENGTH


def test_development_configuration_can_run_without_external_services():
    validate_runtime_configuration(Settings(app_env="development"))


def test_oidc_must_be_configured_as_a_complete_set():
    cfg = Settings(oidc_issuer="https://issuer.example")
    with pytest.raises(RuntimeError, match="incomplète"):
        validate_runtime_configuration(cfg)


def test_only_asymmetric_oidc_algorithms_are_accepted():
    for algorithm in ("none", "HS256", "RS256,HS256"):
        cfg = Settings(oidc_algorithms=algorithm)
        with pytest.raises(RuntimeError, match="RS256"):
            validate_runtime_configuration(cfg)


def test_production_requires_database_oidc_and_explicit_https_cors():
    base = dict(app_env="production", database_url="postgresql://db/app",
                legal_corpus_ingest_database_url="postgresql://cfdt_juris_ingest:secret@db/app",
                platform_admin_database_url="postgresql://cfdt_juris_platform_admin:platform@db/app",
                oidc_issuer="https://issuer.example", oidc_audience="cfdt-juris",
                oidc_jwks_url="https://issuer.example/jwks", aws_endpoint_url_s3="https://storage.example",
                aws_region="us-east-2", aws_access_key_id="test-access", aws_secret_access_key="test-secret",
                document_storage_bucket="cfdt-juris-documents")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        validate_runtime_configuration(Settings(**base))
    with pytest.raises(RuntimeError, match="HTTPS"):
        validate_runtime_configuration(Settings(**base, cors_origins="http://app.example"))
    validate_runtime_configuration(Settings(**base, cors_origins="https://app.example"))


def test_production_rejects_wildcard_cors():
    cfg = Settings(app_env="production", database_url="postgresql://db/app",
        legal_corpus_ingest_database_url="postgresql://cfdt_juris_ingest:secret@db/app",
        platform_admin_database_url="postgresql://cfdt_juris_platform_admin:platform@db/app",
        oidc_issuer="https://issuer.example", oidc_audience="api",
        oidc_jwks_url="https://issuer.example/jwks", cors_origins="*", aws_endpoint_url_s3="https://storage.example",
        aws_region="us-east-2", aws_access_key_id="test-access", aws_secret_access_key="test-secret",
        document_storage_bucket="cfdt-juris-documents")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        validate_runtime_configuration(cfg)


def test_document_and_scanner_limits_are_bounded():
    with pytest.raises(RuntimeError, match="DOCUMENT_MAX_SIZE_MB"):
        validate_runtime_configuration(Settings(document_max_size_mb=0))
    with pytest.raises(RuntimeError, match="ClamAV"):
        validate_runtime_configuration(Settings(clamav_timeout_seconds=90))


def test_bearer_token_size_limit_is_defined():
    assert MAX_BEARER_TOKEN_LENGTH == 16_384


def test_chat_rate_limit_configuration_is_bounded():
    with pytest.raises(RuntimeError, match="CHAT_RATE_LIMIT_PER_MINUTE"):
        validate_runtime_configuration(Settings(chat_rate_limit_per_minute=0))
    with pytest.raises(RuntimeError, match="CHAT_RATE_LIMIT_PER_MINUTE"):
        validate_runtime_configuration(Settings(chat_rate_limit_per_minute=121))
    validate_runtime_configuration(Settings(chat_rate_limit_per_minute=10))
