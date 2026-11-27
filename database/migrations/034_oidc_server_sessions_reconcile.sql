-- Migration 034: reconcile the OIDC server-session schema after legacy
-- Auth0 identity-link migrations occupied historical versions 029 and 030.
BEGIN;

CREATE TABLE IF NOT EXISTS public.oidc_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_token_hash char(64) NOT NULL UNIQUE,
    oidc_issuer text NOT NULL,
    oidc_subject text NOT NULL,
    access_token_ciphertext bytea NOT NULL,
    id_token_ciphertext bytea NOT NULL,
    refresh_token_ciphertext bytea NOT NULL,
    access_expires_at timestamptz NOT NULL,
    refresh_expires_at timestamptz,
    email text,
    email_verified boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    CHECK (length(session_token_hash) = 64)
);

CREATE INDEX IF NOT EXISTS oidc_sessions_subject_active_idx
    ON public.oidc_sessions (oidc_issuer, oidc_subject, last_seen_at DESC)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS oidc_sessions_expiry_idx
    ON public.oidc_sessions (access_expires_at)
    WHERE revoked_at IS NULL;

REVOKE ALL ON public.oidc_sessions FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.oidc_sessions TO cfdt_juris_app;

COMMIT;
