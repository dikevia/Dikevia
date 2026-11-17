from urllib.parse import urlparse
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    debug: bool = False
    database_url: str = ""
    platform_admin_database_url: str = ""
    legal_corpus_ingest_database_url: str = ""
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_algorithms: str = "RS256"
    cors_origins: str = ""
    invitation_base_url: str = ""
    keycloak_admin_base_url: str = ""
    keycloak_admin_realm: str = "cfdt"
    keycloak_admin_client_id: str = "cfdt-juris-provisioner"
    keycloak_admin_client_secret: str = ""
    keycloak_admin_timeout_seconds: float = 8.0
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    document_storage_path: str = "/var/lib/cfdt-juris/documents"
    cgfp_index_path: str = ""
    cgfp_enabled: bool = True
    ai_api_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: float = 25.0
    chat_rate_limit_per_minute: int = 10
    legifrance_environment: str = "sandbox"
    legifrance_client_id: str = ""
    legifrance_client_secret: str = ""
    legifrance_scope: str = "openid"
    legifrance_timeout_seconds: float = 20.0
    legifrance_code_name: str = "Code général de la fonction publique"
    legifrance_cetat_fulltext_enabled: bool = False
    document_max_size_mb: int = 20
    clamav_host: str = "clamav"
    clamav_port: int = 3310
    clamav_timeout_seconds: float = 8.0
    private_instance_mode: bool = False
    private_instance_max_users: int = 10
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_automatic_tax_enabled: bool = True
    billing_success_url: str = "http://localhost:8000/?billing=success"
    billing_cancel_url: str = "http://localhost:8000/?billing=cancel"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def _valid_https_or_local(url: str, allow_http_local: bool) -> bool:
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.hostname:
        return True
    return bool(allow_http_local and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "idp"})


def validate_runtime_configuration(config: Settings) -> None:
    """Fail early on unsafe or incomplete production configuration."""
    if config.app_env not in {"development", "test", "production"}:
        raise RuntimeError("APP_ENV doit être development, test ou production.")
    algorithms = [part.strip() for part in config.oidc_algorithms.split(",") if part.strip()]
    if not algorithms or any(alg not in {"RS256", "ES256"} for alg in algorithms):
        raise RuntimeError("OIDC_ALGORITHMS doit contenir uniquement RS256 et/ou ES256.")
    oidc_values = (config.oidc_issuer, config.oidc_audience, config.oidc_jwks_url)
    if any(oidc_values) and not all(oidc_values):
        raise RuntimeError("Configuration OIDC incomplète : ISSUER, AUDIENCE et JWKS_URL sont requis ensemble.")
    if config.private_instance_mode and config.private_instance_max_users != 10:
        raise RuntimeError("PRIVATE_INSTANCE_MAX_USERS doit être égal à 10 pour l'instance privée CFDT JURIS.")
    if config.private_instance_mode and (config.stripe_secret_key or config.stripe_webhook_secret):
        raise RuntimeError("Stripe doit être entièrement désactivé en mode instance privée.")
    if bool(config.stripe_secret_key) != bool(config.stripe_webhook_secret):
        raise RuntimeError("STRIPE_SECRET_KEY et STRIPE_WEBHOOK_SECRET doivent être configurés ensemble.")
    if config.app_env == "production" and config.stripe_secret_key:
        if not config.stripe_automatic_tax_enabled:
            raise RuntimeError("STRIPE_AUTOMATIC_TAX_ENABLED doit être activé pour les tarifs TTC.")
        for billing_url in (config.billing_success_url, config.billing_cancel_url):
            if not _valid_https_or_local(billing_url, False):
                raise RuntimeError("Les URL de retour Stripe doivent utiliser HTTPS en production.")
    if config.app_env == "production":
        if config.debug:
            raise RuntimeError("DEBUG doit être strictement désactivé en production.")
        if not config.database_url:
            raise RuntimeError("DATABASE_URL est obligatoire en production.")
        if not all(oidc_values):
            raise RuntimeError("OIDC doit être entièrement configuré en production.")
        if not _valid_https_or_local(config.oidc_issuer, False) or not _valid_https_or_local(config.oidc_jwks_url, False):
            raise RuntimeError("ISSUER et JWKS_URL doivent utiliser HTTPS en production.")
        origins = [origin.strip() for origin in config.cors_origins.split(",") if origin.strip()]
        if not origins or "*" in origins:
            raise RuntimeError("CORS_ORIGINS doit lister explicitement les origines autorisées en production.")
        for origin in origins:
            parsed = urlparse(origin)
            if parsed.scheme != "https" or not parsed.hostname or parsed.path not in ("", "/"):
                raise RuntimeError("Chaque origine CORS de production doit être une origine HTTPS valide.")
        if not config.legal_corpus_ingest_database_url:
            raise RuntimeError("LEGAL_CORPUS_INGEST_DATABASE_URL est obligatoire en production pour les imports du corpus juridique.")
        ingest_db = urlparse(config.legal_corpus_ingest_database_url)
        app_db = urlparse(config.database_url)
        if ingest_db.scheme not in {"postgres", "postgresql"} or ingest_db.username != "cfdt_juris_ingest":
            raise RuntimeError("LEGAL_CORPUS_INGEST_DATABASE_URL doit utiliser le rôle PostgreSQL dédié cfdt_juris_ingest.")
        if config.legal_corpus_ingest_database_url == config.database_url or ingest_db.username == app_db.username:
            raise RuntimeError("Le compte d'ingestion doit être distinct du compte PostgreSQL runtime.")
        if not config.platform_admin_database_url:
            raise RuntimeError("PLATFORM_ADMIN_DATABASE_URL est obligatoire en production pour isoler les opérations administrateur.")
        platform_db = urlparse(config.platform_admin_database_url)
        if platform_db.scheme not in {"postgres", "postgresql"} or platform_db.username != "cfdt_juris_platform_admin":
            raise RuntimeError("PLATFORM_ADMIN_DATABASE_URL doit utiliser le rôle dédié cfdt_juris_platform_admin.")
        if config.platform_admin_database_url in {config.database_url, config.legal_corpus_ingest_database_url} or platform_db.username in {app_db.username, ingest_db.username}:
            raise RuntimeError("Le compte administrateur doit être distinct des comptes runtime et ingestion.")
    if config.legifrance_environment not in {"sandbox", "production"}:
        raise RuntimeError("LEGIFRANCE_ENVIRONMENT doit être sandbox ou production.")
    if bool(config.legifrance_client_id) != bool(config.legifrance_client_secret):
        raise RuntimeError("Configuration PISTE incomplète : CLIENT_ID et CLIENT_SECRET sont requis ensemble.")
    if not 2 <= config.legifrance_timeout_seconds <= 60:
        raise RuntimeError("LEGIFRANCE_TIMEOUT_SECONDS doit être compris entre 2 et 60.")
    ai_values = (config.ai_api_base_url, config.ai_api_key, config.ai_model)
    if any(ai_values) and not all(ai_values):
        raise RuntimeError("Configuration IA incomplète : AI_API_BASE_URL, AI_API_KEY et AI_MODEL sont requis ensemble.")
    if config.ai_api_base_url:
        ai_url = urlparse(config.ai_api_base_url)
        if not ai_url.hostname or ai_url.path not in ("", "/v1") or ai_url.query or ai_url.fragment:
            raise RuntimeError("AI_API_BASE_URL doit être une origine ou une base /v1 sans paramètres.")
        if config.app_env == "production" and ai_url.scheme != "https":
            raise RuntimeError("AI_API_BASE_URL doit utiliser HTTPS en production.")
    if not 2 <= config.ai_timeout_seconds <= 120:
        raise RuntimeError("AI_TIMEOUT_SECONDS doit être compris entre 2 et 120.")
    if not 1 <= config.chat_rate_limit_per_minute <= 120:
        raise RuntimeError("CHAT_RATE_LIMIT_PER_MINUTE doit être compris entre 1 et 120.")
    if not 1 <= config.document_max_size_mb <= 100:
        raise RuntimeError("DOCUMENT_MAX_SIZE_MB doit être compris entre 1 et 100.")
    if not 1 <= config.clamav_port <= 65535 or not 1 <= config.clamav_timeout_seconds <= 60:
        raise RuntimeError("Configuration ClamAV invalide.")
    admin_values = (config.keycloak_admin_base_url, config.keycloak_admin_client_secret)
    if any(admin_values) and not all(admin_values):
        raise RuntimeError("Configuration Keycloak Admin incomplète : URL et secret requis ensemble.")
    if config.keycloak_admin_base_url:
        admin_url = urlparse(config.keycloak_admin_base_url)
        if not admin_url.hostname or admin_url.query or admin_url.fragment or admin_url.path not in ("", "/"):
            raise RuntimeError("KEYCLOAK_ADMIN_BASE_URL doit être une origine sans chemin, paramètres ni fragment.")
        if config.app_env == "production" and admin_url.scheme != "https":
            raise RuntimeError("KEYCLOAK_ADMIN_BASE_URL doit utiliser HTTPS en production.")
        if config.app_env != "production" and admin_url.scheme not in {"http", "https"}:
            raise RuntimeError("KEYCLOAK_ADMIN_BASE_URL doit utiliser HTTP ou HTTPS.")
    if not 1 <= config.keycloak_admin_timeout_seconds <= 30:
        raise RuntimeError("KEYCLOAK_ADMIN_TIMEOUT_SECONDS doit être compris entre 1 et 30.")
    smtp_values = (config.smtp_host, config.smtp_from)
    if any(smtp_values) and not all(smtp_values):
        raise RuntimeError("Configuration SMTP incomplète : hôte et adresse expéditeur requis.")
    if not 1 <= config.smtp_port <= 65535:
        raise RuntimeError("SMTP_PORT invalide.")
    automation_requested = any((config.keycloak_admin_base_url, config.keycloak_admin_client_secret,
                                config.smtp_host, config.smtp_from))
    if automation_requested:
        if not all((config.keycloak_admin_base_url, config.keycloak_admin_client_secret,
                    config.smtp_host, config.smtp_from, config.invitation_base_url)):
            raise RuntimeError("Invitations automatisées : Keycloak Admin, SMTP et INVITATION_BASE_URL doivent être configurés ensemble.")
        if not _valid_https_or_local(config.invitation_base_url, config.app_env != "production"):
            raise RuntimeError("INVITATION_BASE_URL doit utiliser HTTPS en production (HTTP localhost autorisé en développement).")


settings = Settings()
