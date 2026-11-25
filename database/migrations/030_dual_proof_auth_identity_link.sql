-- Dual-proof account linking: Auth0 session + fresh Keycloak ID token.
-- This migration preserves users.id, roles, memberships, subscriptions and entitlements.
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=current_user AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Migration 030 requires a DBA/BYPASSRLS owner';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cfdt_juris_app') THEN
    RAISE EXCEPTION 'Runtime role cfdt_juris_app is missing';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.auth_identity_link_challenges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  auth0_issuer text NOT NULL,
  auth0_subject text NOT NULL,
  nonce_hash char(64) NOT NULL UNIQUE CHECK (nonce_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '5 minutes'),
  consumed_at timestamptz,
  CHECK (expires_at > created_at)
);
CREATE INDEX IF NOT EXISTS auth_identity_link_challenges_expiry_idx
  ON public.auth_identity_link_challenges(expires_at);

REVOKE ALL ON public.auth_identity_link_challenges FROM PUBLIC, cfdt_juris_app;

CREATE OR REPLACE FUNCTION public.create_auth_identity_link_challenge(
  p_auth0_issuer text, p_auth0_subject text, p_nonce_hash text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
DECLARE expected_auth0_issuer constant text := 'https://dev-brlgaz1yh2de3mjo.us.auth0.com/';
BEGIN
  IF p_auth0_issuer IS DISTINCT FROM expected_auth0_issuer
     OR p_auth0_subject IS NULL OR length(p_auth0_subject) NOT BETWEEN 1 AND 255
     OR p_nonce_hash IS NULL OR p_nonce_hash !~ '^[0-9a-f]{64}$' THEN
    RETURN false;
  END IF;
  IF EXISTS (SELECT 1 FROM users WHERE oidc_issuer=p_auth0_issuer AND oidc_subject=p_auth0_subject) THEN
    -- Already provisioned accounts do not need identity migration.
    RETURN false;
  END IF;
  INSERT INTO auth_identity_link_challenges(auth0_issuer,auth0_subject,nonce_hash)
  VALUES(p_auth0_issuer,p_auth0_subject,p_nonce_hash);
  RETURN true;
END;
$$;

CREATE OR REPLACE FUNCTION public.link_auth_identity_after_dual_proof(
  p_auth0_issuer text, p_auth0_subject text,
  p_legacy_issuer text, p_legacy_subject text, p_nonce_hash text
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
DECLARE
  linked_user_id uuid;
  challenge_id uuid;
  expected_auth0_issuer constant text := 'https://dev-brlgaz1yh2de3mjo.us.auth0.com/';
  expected_legacy_issuer constant text := 'https://dikevia-identity-l2r8.onrender.com/realms/cfdt';
BEGIN
  IF p_auth0_issuer IS DISTINCT FROM expected_auth0_issuer
     OR p_legacy_issuer IS DISTINCT FROM expected_legacy_issuer
     OR p_auth0_subject IS NULL OR length(p_auth0_subject) NOT BETWEEN 1 AND 255
     OR p_legacy_subject IS NULL OR length(p_legacy_subject) NOT BETWEEN 1 AND 255
     OR p_nonce_hash IS NULL OR p_nonce_hash !~ '^[0-9a-f]{64}$' THEN
    RETURN NULL;
  END IF;

  SELECT id INTO challenge_id
  FROM auth_identity_link_challenges
  WHERE auth0_issuer=p_auth0_issuer AND auth0_subject=p_auth0_subject
    AND nonce_hash=p_nonce_hash AND consumed_at IS NULL AND expires_at > now()
  FOR UPDATE;
  IF challenge_id IS NULL THEN RETURN NULL; END IF;

  -- An Auth0 identity may not be moved between internal accounts.
  IF EXISTS (SELECT 1 FROM users WHERE oidc_issuer=p_auth0_issuer AND oidc_subject=p_auth0_subject) THEN
    RETURN NULL;
  END IF;

  SELECT id INTO linked_user_id
  FROM users
  WHERE oidc_issuer=p_legacy_issuer AND oidc_subject=p_legacy_subject AND status='ACTIVE'
  FOR UPDATE;
  IF linked_user_id IS NULL THEN RETURN NULL; END IF;

  UPDATE users SET oidc_issuer=p_auth0_issuer, oidc_subject=p_auth0_subject
  WHERE id=linked_user_id AND oidc_issuer=p_legacy_issuer
    AND oidc_subject=p_legacy_subject AND status='ACTIVE';
  IF NOT FOUND THEN RETURN NULL; END IF;

  UPDATE auth_identity_link_challenges SET consumed_at=now() WHERE id=challenge_id;
  RETURN linked_user_id;
END;
$$;

REVOKE ALL ON FUNCTION public.create_auth_identity_link_challenge(text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.link_auth_identity_after_dual_proof(text,text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.create_auth_identity_link_challenge(text,text,text) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION public.link_auth_identity_after_dual_proof(text,text,text,text,text) TO cfdt_juris_app;

COMMIT;
