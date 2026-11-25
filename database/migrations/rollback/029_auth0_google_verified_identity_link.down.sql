-- Remove the narrowly scoped Auth0 Google linking function.
-- Any identity link already performed is intentionally not reversed automatically.
REVOKE ALL ON FUNCTION public.link_auth0_google_legacy_user(text,text,text,boolean) FROM PUBLIC;
DROP FUNCTION IF EXISTS public.link_auth0_google_legacy_user(text,text,text,boolean);
