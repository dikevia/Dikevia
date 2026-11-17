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
 original_filename text,mime_type text,file_size_bytes bigint,uploaded_by uuid REFERENCES users(id),validation_note text,
 scan_status text NOT NULL DEFAULT 'NOT_SCANNED' CHECK(scan_status IN('NOT_SCANNED','CLEAN','INFECTED')),scan_engine text,scanned_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(organization_id,id),
 FOREIGN KEY(organization_id,collectivity_id) REFERENCES collectivities(organization_id,id));
CREATE TABLE document_versions(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 document_id uuid NOT NULL,version_number integer NOT NULL CHECK(version_number>0),storage_key text,sha256 char(64),
 source_url text,effective_from date,effective_to date,created_at timestamptz NOT NULL DEFAULT now(),
 original_filename text,mime_type text,file_size_bytes bigint,uploaded_by uuid REFERENCES users(id),
 scan_status text NOT NULL DEFAULT 'NOT_SCANNED' CHECK(scan_status IN('NOT_SCANNED','CLEAN','INFECTED')),scan_engine text,scanned_at timestamptz,
 UNIQUE(organization_id,document_id,version_number),
 FOREIGN KEY(organization_id,document_id) REFERENCES documents(organization_id,id));
CREATE TABLE document_text (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),organization_id uuid NOT NULL,document_id uuid NOT NULL,
 version_number integer NOT NULL,sha256 char(64) NOT NULL,extracted_text text NOT NULL DEFAULT '',
 extraction_status text NOT NULL CHECK(extraction_status IN('EXTRACTED','NO_TEXT','ENCRYPTED','TOO_LARGE_TO_EXTRACT','FAILED','UNSUPPORTED')),
 search_vector tsvector NOT NULL DEFAULT ''::tsvector,created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(organization_id,document_id,version_number),
 FOREIGN KEY(organization_id,document_id,version_number) REFERENCES document_versions(organization_id,document_id,version_number) ON DELETE CASCADE);
CREATE OR REPLACE FUNCTION document_text_set_search_vector() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.search_vector := to_tsvector('french',coalesce(NEW.extracted_text,'')); RETURN NEW; END; $$;
CREATE TRIGGER document_text_search_vector_trigger BEFORE INSERT OR UPDATE OF extracted_text ON document_text
 FOR EACH ROW EXECUTE FUNCTION document_text_set_search_vector();
CREATE INDEX document_text_search_vector_gin ON document_text USING GIN(search_vector);
CREATE INDEX document_text_org_document_idx ON document_text(organization_id,document_id,version_number DESC);
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
 current_period_end timestamptz,cancel_at_period_end boolean NOT NULL DEFAULT false,
 free_access_until timestamptz,admin_note text,updated_at timestamptz NOT NULL DEFAULT now(),
 created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE billing_webhook_events(
 provider_event_id text PRIMARY KEY,event_type text NOT NULL,processed_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE audit_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 actor_user_id uuid REFERENCES users(id),event_type text NOT NULL,target_type text,target_id uuid,
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb,created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX audit_org_created_idx ON audit_events(organization_id,created_at DESC);
CREATE INDEX documents_org_collectivity_created_idx ON documents(organization_id,collectivity_id,created_at DESC);
CREATE INDEX document_versions_org_document_idx ON document_versions(organization_id,document_id,version_number DESC);

DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['organizations','memberships','collectivities','documents','document_versions','document_text',
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
 FOREACH t IN ARRAY ARRAY['collectivities','documents','document_versions','document_text','document_relations',
 'organization_settings','subscriptions','audit_events']
 LOOP EXECUTE format('CREATE POLICY %I ON %I USING(organization_id=NULLIF(current_setting(''app.current_org_id'',true),'''')::uuid) WITH CHECK(organization_id=NULLIF(current_setting(''app.current_org_id'',true),'''')::uuid)',t||'_tenant_isolation',t);
 END LOOP;
END $$;
CREATE POLICY invitations_tenant_isolation ON invitations
 USING(organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid
       OR token_hash=NULLIF(current_setting('app.invitation_token_hash',true),''))
 WITH CHECK(organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid);

-- V3.2: global identity tables are private too; only the current OIDC identity
-- is visible to the runtime role.
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_self_identity ON users FOR ALL
 USING (oidc_issuer=NULLIF(current_setting('app.oidc_issuer',true),'')
    AND oidc_subject=NULLIF(current_setting('app.oidc_subject',true),''))
 WITH CHECK (oidc_issuer=NULLIF(current_setting('app.oidc_issuer',true),'')
    AND oidc_subject=NULLIF(current_setting('app.oidc_subject',true),''));
ALTER TABLE platform_admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_admins FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_admins_self_read ON platform_admins FOR SELECT
 USING (user_id IN (SELECT id FROM users
   WHERE oidc_issuer=NULLIF(current_setting('app.oidc_issuer',true),'')
     AND oidc_subject=NULLIF(current_setting('app.oidc_subject',true),'')
     AND status='ACTIVE'));
CREATE POLICY platform_admins_bootstrap_insert ON platform_admins FOR INSERT
 WITH CHECK (user_id IN (SELECT id FROM users
   WHERE oidc_issuer=NULLIF(current_setting('app.oidc_issuer',true),'')
     AND oidc_subject=NULLIF(current_setting('app.oidc_subject',true),'')
     AND status='ACTIVE'));
CREATE UNIQUE INDEX invitations_token_hash_uq ON invitations(token_hash);
CREATE INDEX invitations_org_status_idx ON invitations(organization_id,status,expires_at);
CREATE UNIQUE INDEX invitations_one_pending_per_email_uq ON invitations(organization_id,lower(email_normalized)) WHERE status='PENDING';

-- Administrative reporting crosses tenant boundaries only through these narrowly
-- scoped SECURITY DEFINER functions. The migration owner must be a DBA/BYPASSRLS
-- role; the runtime role receives EXECUTE only, never broad table access.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=current_user AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Schema initialization requires a DBA role with BYPASSRLS';
  END IF;
END $$;
CREATE OR REPLACE FUNCTION platform_admin_list_organizations(p_user_id uuid)
RETURNS TABLE(
  id uuid, slug text, legal_name text, display_name text, organization_status text,
  plan_code text, subscription_status text, active_users bigint, pending_invitations bigint,
  created_at timestamptz, current_period_end timestamptz, free_access_until timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id = p_user_id) THEN
    RAISE EXCEPTION 'platform administrator required' USING ERRCODE = '42501';
  END IF;
  RETURN QUERY
    SELECT o.id, o.slug, o.legal_name, o.display_name, o.status,
      COALESCE(s.plan_code, o.plan_code), COALESCE(s.status, 'FOUNDING_FREE'),
      (SELECT count(*) FROM memberships m WHERE m.organization_id=o.id AND m.status='ACTIVE'),
      (SELECT count(*) FROM invitations i WHERE i.organization_id=o.id AND i.status='PENDING' AND i.expires_at>now()),
      o.created_at, s.current_period_end, s.free_access_until
    FROM organizations o LEFT JOIN subscriptions s ON s.organization_id=o.id
    ORDER BY o.created_at DESC;
END;
$$;

CREATE OR REPLACE FUNCTION platform_admin_set_organization_status(
  p_user_id uuid, p_organization_id uuid, p_status text
) RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
DECLARE changed_id uuid;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id = p_user_id) THEN
    RAISE EXCEPTION 'platform administrator required' USING ERRCODE = '42501';
  END IF;
  IF p_status NOT IN ('ACTIVE','SUSPENDED') THEN
    RAISE EXCEPTION 'invalid organization status' USING ERRCODE = '22023';
  END IF;
  UPDATE organizations SET status=p_status WHERE id=p_organization_id RETURNING id INTO changed_id;
  IF changed_id IS NULL THEN RETURN false; END IF;
  PERFORM set_config('app.current_org_id', p_organization_id::text, true);
  INSERT INTO audit_events(organization_id, actor_user_id, event_type, target_type, target_id, metadata)
  VALUES(p_organization_id, p_user_id,
    CASE WHEN p_status='SUSPENDED' THEN 'ORGANIZATION_SUSPENDED' ELSE 'ORGANIZATION_REACTIVATED' END,
    'organization', p_organization_id, jsonb_build_object('status',p_status));
  RETURN true;
END;
$$;

REVOKE ALL ON FUNCTION platform_admin_list_organizations(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_admin_set_organization_status(uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION platform_admin_list_organizations(uuid) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_set_organization_status(uuid,uuid,text) TO cfdt_juris_app;

COMMIT;


-- V3.21 permanent legal knowledge base
-- V3.21 — Référentiel juridique national partagé (sources publiques officielles).
-- Les tables de ce référentiel sont communes à tous les tenants ; les documents
-- propres aux collectivités restent dans les tables tenant-scoped existantes.
BEGIN;
CREATE TABLE IF NOT EXISTS legal_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type text NOT NULL CHECK (source_type IN ('LEGIFRANCE_LEGI','LEGIFRANCE_LODA','LEGIFRANCE_CETAT','DILA_CIRCULAIRES','LEGIFRANCE_JORF','OTHER_OFFICIAL','CGFP_SNAPSHOT')),
  source_id text NOT NULL,
  title text NOT NULL,
  document_kind text NOT NULL CHECK (document_kind IN ('CODE','LAW','ORDONNANCE','DECREE','ORDER','CIRCULAR','ADMIN_CASELAW','JOURNAL_OFFICIEL','OTHER')),
  official_number text,
  jurisdiction text,
  publisher text,
  official_url text,
  signature_date date,
  publication_date date,
  status text NOT NULL DEFAULT 'UNKNOWN' CHECK (status IN ('IN_FORCE','REPEALED','REPLACED','NOT_IN_FORCE','UNKNOWN','PARTIAL')),
  source_status text NOT NULL DEFAULT 'METADATA_ONLY' CHECK (source_status IN ('METADATA_ONLY','OFFICIAL_TEXT_RETRIEVED','OFFICIAL_TEXT_ID_VERIFIED','OFFICIAL_XML_IMPORTED','IMPORTED_UNVERIFIED','MANUALLY_VERIFIED')),
  raw_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  content_sha256 char(64),
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(source_type, source_id)
);
CREATE INDEX IF NOT EXISTS legal_documents_kind_status_idx ON legal_documents(document_kind,status);
CREATE INDEX IF NOT EXISTS legal_documents_number_idx ON legal_documents(official_number);

CREATE TABLE IF NOT EXISTS legal_document_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
  version_key text NOT NULL,
  source_version_id text,
  valid_from date,
  valid_to date,
  version_status text NOT NULL DEFAULT 'UNKNOWN' CHECK (version_status IN ('IN_FORCE','REPEALED','REPLACED','NOT_IN_FORCE','UNKNOWN')),
  full_text text NOT NULL DEFAULT '',
  text_sha256 char(64),
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(document_id, version_key)
);
CREATE INDEX IF NOT EXISTS legal_versions_dates_idx ON legal_document_versions(valid_from,valid_to);
CREATE INDEX IF NOT EXISTS legal_versions_document_idx ON legal_document_versions(document_id,valid_from DESC);

CREATE TABLE IF NOT EXISTS legal_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version_id uuid NOT NULL REFERENCES legal_document_versions(id) ON DELETE CASCADE,
  ordinal integer NOT NULL CHECK (ordinal >= 0),
  anchor text,
  content_kind text NOT NULL DEFAULT 'FULL_TEXT' CHECK (content_kind IN ('FULL_TEXT','METADATA')),
  content text NOT NULL,
  search_vector tsvector NOT NULL DEFAULT ''::tsvector,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(version_id,ordinal)
);
CREATE OR REPLACE FUNCTION legal_chunks_set_search_vector() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.search_vector := to_tsvector('french',coalesce(NEW.anchor,'') || ' ' || coalesce(NEW.content,'')); RETURN NEW; END; $$;
DROP TRIGGER IF EXISTS legal_chunks_search_vector_trigger ON legal_chunks;
CREATE TRIGGER legal_chunks_search_vector_trigger BEFORE INSERT OR UPDATE OF anchor,content ON legal_chunks
 FOR EACH ROW EXECUTE FUNCTION legal_chunks_set_search_vector();
CREATE INDEX IF NOT EXISTS legal_chunks_search_vector_gin ON legal_chunks USING GIN(search_vector);

CREATE TABLE IF NOT EXISTS legal_document_relations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_document_id uuid NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
  target_document_id uuid NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
  relation_type text NOT NULL CHECK (relation_type IN ('AMENDS','AMENDED_BY','REPEALS','REPEALED_BY','REPLACES','REPLACED_BY','APPLIES','INTERPRETS','CITES','RELATED')),
  source_reference text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(source_document_id,target_document_id,relation_type)
);

CREATE TABLE IF NOT EXISTS legal_ingestion_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type text NOT NULL,
  run_mode text NOT NULL CHECK (run_mode IN ('SEARCH_IMPORT','BULK_XML_IMPORT','FULL_REFRESH','INCREMENTAL_REFRESH')),
  status text NOT NULL CHECK (status IN ('RUNNING','SUCCEEDED','PARTIAL','FAILED')),
  query_text text,
  records_seen integer NOT NULL DEFAULT 0,
  records_imported integer NOT NULL DEFAULT 0,
  records_rejected integer NOT NULL DEFAULT 0,
  error_summary text,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE INDEX IF NOT EXISTS legal_ingestion_runs_started_idx ON legal_ingestion_runs(started_at DESC);

-- Référentiel public commun : lecture pour tous les utilisateurs authentifiés
-- (via l'API), écriture réservée aux opérations d'ingestion contrôlées.
GRANT SELECT ON legal_documents,legal_document_versions,legal_chunks,legal_document_relations,legal_ingestion_runs TO cfdt_juris_app;
-- Writes are isolated to a dedicated ingestion DB role. The ordinary API role is read-only.
GRANT SELECT ON legal_documents,legal_document_versions,legal_chunks,legal_document_relations,legal_ingestion_runs TO cfdt_juris_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON legal_documents,legal_document_versions,legal_chunks,legal_document_relations,legal_ingestion_runs TO cfdt_juris_ingest;
COMMIT;



-- Migration registry: created/managed by scripts/db_migrate.py.
-- No runtime application grants are intentionally provided.
CREATE TABLE IF NOT EXISTS schema_migrations (
  version integer PRIMARY KEY,
  name text NOT NULL,
  checksum char(64) NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now(),
  applied_by text NOT NULL DEFAULT current_user
);
REVOKE ALL ON schema_migrations FROM PUBLIC;
