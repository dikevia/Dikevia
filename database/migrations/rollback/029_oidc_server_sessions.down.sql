-- Rollback for 029_oidc_server_sessions.sql.
-- This removes all server-side OIDC sessions and invalidates their cookies.
BEGIN;
REVOKE ALL ON TABLE oidc_sessions FROM PUBLIC;
REVOKE ALL ON TABLE oidc_sessions FROM cfdt_juris_app;
DROP INDEX IF EXISTS oidc_sessions_subject_active_idx;
DROP INDEX IF EXISTS oidc_sessions_expiry_idx;
DROP TABLE IF EXISTS oidc_sessions;
COMMIT;
