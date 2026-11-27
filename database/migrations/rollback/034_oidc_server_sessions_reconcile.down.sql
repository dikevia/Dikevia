-- Explicit rollback for migration 034. This removes stored OIDC sessions.
BEGIN;
DROP TABLE IF EXISTS public.oidc_sessions;
COMMIT;
