-- V3.39: narrowly scoped, verified-email linking for Auth0 Google identities.
-- This migration is intentionally constrained to the staging Auth0 tenant.
-- Production must receive its own reviewed migration/configuration before rollout.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname = current_user AND (rolsuper OR rolbypassrls)
  ) THEN
    RAISE EXCEPTION 'Migration 029 requires a DBA/BYPASSRLS owner for the SECURITY DEFINER function';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cfdt_juris_app') THEN
    RAISE EXCEPTION 'Runtime role cfdt_juris_app is missing';
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.link_auth0_google_legacy_user(
  p_issuer text,
  p_subject text,
  p_email text,
  p_email_verified boolean
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
DECLARE
  matched_user_id uuid;
  candidate_count integer;
  expected_auth0_issuer constant text := 'https://dev-brlgaz1yh2de3mjo.us.auth0.com/';
  expected_legacy_issuer constant text := 'https://dikevia-identity-l2r8.onrender.com/realms/cfdt';
BEGIN
  -- Fail closed: this function is only valid for the explicitly named staging tenant.
  IF p_issuer IS DISTINCT FROM expected_auth0_issuer
     OR p_email_verified IS DISTINCT FROM true
     OR p_email IS NULL
     OR length(btrim(p_email)) NOT BETWEEN 3 AND 320
     OR p_subject IS NULL
     OR p_subject NOT LIKE 'google-oauth2|%'
     OR length(p_subject) > 255 THEN
    RETURN NULL;
  END IF;

  -- Never reassign an Auth0 identity already attached to any account.
  IF EXISTS (
    SELECT 1 FROM users
    WHERE oidc_issuer = expected_auth0_issuer AND oidc_subject = p_subject
  ) THEN
    RETURN NULL;
  END IF;

  SELECT count(*) INTO candidate_count
  FROM users
  WHERE oidc_issuer = expected_legacy_issuer
    AND status = 'ACTIVE'
    AND email IS NOT NULL
    AND lower(btrim(email)) = lower(btrim(p_email));

  -- Missing, duplicate, suspended, or ambiguous legacy accounts are not linked.
  IF candidate_count <> 1 THEN
    RETURN NULL;
  END IF;

  SELECT id INTO matched_user_id
  FROM users
  WHERE oidc_issuer = expected_legacy_issuer
    AND status = 'ACTIVE'
    AND email IS NOT NULL
    AND lower(btrim(email)) = lower(btrim(p_email))
  FOR UPDATE;

  IF matched_user_id IS NULL THEN
    RETURN NULL;
  END IF;

  -- Preserve the internal UUID and every role, membership, entitlement and tenant row.
  UPDATE users
  SET oidc_issuer = expected_auth0_issuer,
      oidc_subject = p_subject
  WHERE id = matched_user_id
    AND oidc_issuer = expected_legacy_issuer
    AND status = 'ACTIVE';

  IF NOT FOUND THEN
    RETURN NULL;
  END IF;

  RETURN matched_user_id;
END;
$$;

REVOKE ALL ON FUNCTION public.link_auth0_google_legacy_user(text,text,text,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.link_auth0_google_legacy_user(text,text,text,boolean) TO cfdt_juris_app;
