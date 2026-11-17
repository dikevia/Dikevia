BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE organizations(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), slug text NOT NULL UNIQUE,
 legal_name text NOT NULL, display_name text NOT NULL,
 status text NOT NULL DEFAULT 'ACTIVE' CHECK(status IN('ACTIVE','SUSPENDED','CLOSED')),
 plan_code text NOT NULL DEFAULT 'FOUNDING_FREE', created_at timestamptz NOT NULL DEFAULT now());
-- Registre d'identité minimal global, distinct des données métiers par organisation.
CREATE TABLE users(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), oidc_issuer text NOT NULL, oidc_subject text NOT NULL,
 email text, display_name text, status text NOT NULL DEFAULT 'ACTIVE' CHECK(status IN('ACTIVE','DISABLED')),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(oidc_issuer,oidc_subject));
CREATE TABLE platform_admins(user_id uuid PRIMARY KEY REFERENCES users(id),created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE memberships(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 role text NOT NULL CHECK(role IN('ORG_ADMIN','LEGAL_EDITOR','MEMBER')),
 status text NOT NULL DEFAULT 'INVITED' CHECK(status IN('INVITED','ACTIVE','REVOKED')),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(organization_id,user_id), UNIQUE(organization_id,id));
CREATE INDEX memberships_user_status_idx ON memberships(user_id,status);
CREATE TABLE collectivities(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 code text NOT NULL,name text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(organization_id,code),UNIQUE(organization_id,id));
CREATE TABLE documents(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 collectivity_id uuid NOT NULL,title text NOT NULL,document_type text NOT NULL,official_number text,
 adopted_at date,published_at date,effective_from date,effective_to date,official_url text,storage_key text,sha256 char(64),
 validation_status text NOT NULL CHECK(validation_status IN('TO_COLLECT','COLLECTED_UNVERIFIED','VERIFIED_APPLICABLE','VERIFIED_HISTORICAL','REPEALED','REPLACED','INCOMPLETE')),
 annexes_complete boolean NOT NULL DEFAULT false,validated_by uuid REFERENCES users(id),validated_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(organization_id,id),
 FOREIGN KEY(organization_id,collectivity_id) REFERENCES collectivities(organization_id,id));
CREATE TABLE document_versions(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 document_id uuid NOT NULL,version_number integer NOT NULL CHECK(version_number>0),storage_key text,sha256 char(64),
 source_url text,effective_from date,effective_to date,created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(organization_id,document_id,version_number),
 FOREIGN KEY(organization_id,document_id) REFERENCES documents(organization_id,id));
CREATE TABLE document_relations(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 source_document_id uuid NOT NULL,target_document_id uuid NOT NULL,
 relation_type text NOT NULL CHECK(relation_type IN('AMENDS','AMENDED_BY','REPEALS','REPEALED_BY','REPLACES','REPLACED_BY','ANNEX_OF')),
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(organization_id,source_document_id,target_document_id,relation_type),
 FOREIGN KEY(organization_id,source_document_id) REFERENCES documents(organization_id,id),
 FOREIGN KEY(organization_id,target_document_id) REFERENCES documents(organization_id,id));
CREATE TABLE invitations(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 email_normalized text NOT NULL,role text NOT NULL CHECK(role IN('ORG_ADMIN','LEGAL_EDITOR','MEMBER')),
 invited_by uuid NOT NULL REFERENCES users(id),status text NOT NULL CHECK(status IN('PENDING','ACCEPTED','EXPIRED','REVOKED')),
 token_hash text NOT NULL,expires_at timestamptz NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE organization_settings(
 organization_id uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
 settings jsonb NOT NULL DEFAULT '{}'::jsonb,updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE subscriptions(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),organization_id uuid NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
 provider text,provider_customer_id text,provider_subscription_id text,plan_code text NOT NULL DEFAULT 'FOUNDING_FREE',
 status text NOT NULL CHECK(status IN('FOUNDING_FREE','TRIAL','ACTIVE','PAST_DUE','CANCELED','SUSPENDED')),
 current_period_end timestamptz,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE audit_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 actor_user_id uuid REFERENCES users(id),event_type text NOT NULL,target_type text,target_id uuid,
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb,created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX audit_org_created_idx ON audit_events(organization_id,created_at DESC);

DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['organizations','memberships','collectivities','documents','document_versions',
 'document_relations','invitations','organization_settings','subscriptions','audit_events']
 LOOP EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
       EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t); END LOOP;
END $$;

CREATE POLICY organizations_isolation ON organizations
 USING(id=NULLIF(current_setting('app.current_org_id',true),'')::uuid OR EXISTS(
  SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id
  WHERE m.organization_id=organizations.id AND m.status='ACTIVE' AND u.status='ACTIVE'
   AND u.oidc_issuer=NULLIF(current_setting('app.oidc_issuer',true),'')
   AND u.oidc_subject=NULLIF(current_setting('app.oidc_subject',true),'')))
 WITH CHECK(id=NULLIF(current_setting('app.current_org_id',true),'')::uuid);
CREATE POLICY memberships_isolation ON memberships
 USING(organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid OR user_id=(
  SELECT id FROM users WHERE oidc_issuer=NULLIF(current_setting('app.oidc_issuer',true),'')
   AND oidc_subject=NULLIF(current_setting('app.oidc_subject',true),'') AND status='ACTIVE'))
 WITH CHECK(organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['collectivities','documents','document_versions','document_relations',
 'invitations','organization_settings','subscriptions','audit_events']
 LOOP EXECUTE format('CREATE POLICY %I ON %I USING(organization_id=NULLIF(current_setting(''app.current_org_id'',true),'''')::uuid) WITH CHECK(organization_id=NULLIF(current_setting(''app.current_org_id'',true),'''')::uuid)',t||'_tenant_isolation',t);
 END LOOP;
END $$;
COMMIT;
