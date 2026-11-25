-- Drop dual-proof link challenge infrastructure. Do not automatically undo identity links.
BEGIN;
REVOKE ALL ON FUNCTION public.create_auth_identity_link_challenge(text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.link_auth_identity_after_dual_proof(text,text,text,text,text) FROM PUBLIC;
DROP FUNCTION IF EXISTS public.create_auth_identity_link_challenge(text,text,text);
DROP FUNCTION IF EXISTS public.link_auth_identity_after_dual_proof(text,text,text,text,text);
DROP TABLE IF EXISTS public.auth_identity_link_challenges;
COMMIT;
