-- Run ONCE as the migration/DBA role. Supply verified OIDC identity values via psql variables:
-- psql ... -v oidc_issuer='https://...' -v oidc_subject='immutable-subject' -v email='admin@example.org'
-- Never expose this script through an API endpoint or grant the runtime role INSERT on platform_admins.
BEGIN;
-- Required because FORCE ROW LEVEL SECURITY also applies to table owners.
SELECT set_config('app.oidc_issuer', :'oidc_issuer', true);
SELECT set_config('app.oidc_subject', :'oidc_subject', true);
INSERT INTO users(oidc_issuer, oidc_subject, email, display_name, status)
VALUES (:'oidc_issuer', :'oidc_subject', :'email', 'Administrateur plateforme', 'ACTIVE')
ON CONFLICT (oidc_issuer, oidc_subject)
DO UPDATE SET email=EXCLUDED.email
RETURNING id \gset
INSERT INTO platform_admins(user_id) VALUES (:'id')
ON CONFLICT (user_id) DO NOTHING;
COMMIT;
