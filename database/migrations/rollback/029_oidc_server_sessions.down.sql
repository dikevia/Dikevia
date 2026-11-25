BEGIN;
REVOKE ALL ON oidc_sessions FROM cfdt_juris_app;
DROP TABLE IF EXISTS oidc_sessions;
COMMIT;
