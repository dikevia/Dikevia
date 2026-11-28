BEGIN;

-- A session dossier is an organisation-level working record, distinct from
-- a private conversation-bound legal dossier. Tenant members collaborate on it.
CREATE TABLE instance_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by uuid NOT NULL REFERENCES users(id),
    instance_code text NOT NULL CHECK (instance_code IN ('CST','CAP','CCP','F3SCT')),
    title text NOT NULL CHECK (char_length(title) BETWEEN 3 AND 200),
    meeting_date date,
    meeting_status text NOT NULL DEFAULT 'PREPARATION'
      CHECK (meeting_status IN ('PREPARATION','CONVOQUEE','TENUE','COMPTE_RENDU_A_VALIDER','CLOTUREE')),
    agenda jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(agenda)='array'),
    preparation jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(preparation)='object'),
    questions jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(questions)='array'),
    documents jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(documents)='array'),
    minutes text NOT NULL DEFAULT '' CHECK (char_length(minutes) <= 50000),
    action_items jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(action_items)='array'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id,id)
);
CREATE INDEX instance_sessions_org_date_idx
    ON instance_sessions(organization_id, meeting_date DESC NULLS LAST, updated_at DESC);
CREATE INDEX instance_sessions_org_status_idx
    ON instance_sessions(organization_id, meeting_status, updated_at DESC);

ALTER TABLE instance_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE instance_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY instance_sessions_tenant_isolation ON instance_sessions
    USING (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
    WITH CHECK (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON instance_sessions TO cfdt_juris_app;
COMMIT;
