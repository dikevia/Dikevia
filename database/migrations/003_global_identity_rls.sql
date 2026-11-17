BEGIN;
-- The identity registry is global, but it is not a public directory.
-- The runtime role may see and modify only the identity matching the
-- issuer/subject established by the API after OIDC token verification.
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS users_self_identity ON users;
CREATE POLICY users_self_identity ON users
  FOR ALL
  USING (
    oidc_issuer = NULLIF(current_setting('app.oidc_issuer', true), '')
    AND oidc_subject = NULLIF(current_setting('app.oidc_subject', true), '')
  )
  WITH CHECK (
    oidc_issuer = NULLIF(current_setting('app.oidc_issuer', true), '')
    AND oidc_subject = NULLIF(current_setting('app.oidc_subject', true), '')
  );

-- A platform-admin marker is readable only for the authenticated user's own
-- identity. The runtime role receives no INSERT/UPDATE/DELETE permission here.
ALTER TABLE platform_admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_admins FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS platform_admins_self_read ON platform_admins;
CREATE POLICY platform_admins_self_read ON platform_admins
  FOR SELECT
  USING (
    user_id IN (
      SELECT id FROM users
      WHERE oidc_issuer = NULLIF(current_setting('app.oidc_issuer', true), '')
        AND oidc_subject = NULLIF(current_setting('app.oidc_subject', true), '')
        AND status = 'ACTIVE'
    )
  );
-- A trusted DBA can bootstrap only the admin marker for the identity it has
-- explicitly set in this session. The API role has no INSERT grant.
DROP POLICY IF EXISTS platform_admins_bootstrap_insert ON platform_admins;
CREATE POLICY platform_admins_bootstrap_insert ON platform_admins
  FOR INSERT
  WITH CHECK (
    user_id IN (
      SELECT id FROM users
      WHERE oidc_issuer = NULLIF(current_setting('app.oidc_issuer', true), '')
        AND oidc_subject = NULLIF(current_setting('app.oidc_subject', true), '')
        AND status = 'ACTIVE'
    )
  );

-- Invitation hashes must be unique: acceptance must resolve to exactly one row.
CREATE UNIQUE INDEX IF NOT EXISTS invitations_token_hash_uq ON invitations(token_hash);
CREATE INDEX IF NOT EXISTS invitations_org_status_idx ON invitations(organization_id, status, expires_at);
COMMIT;
