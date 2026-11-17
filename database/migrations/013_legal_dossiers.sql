BEGIN;
CREATE TABLE legal_dossiers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (conversation_id),
    FOREIGN KEY (organization_id, conversation_id)
      REFERENCES chat_conversations(organization_id, id) ON DELETE CASCADE
);
CREATE INDEX legal_dossiers_owner_idx ON legal_dossiers(organization_id,user_id,updated_at DESC);
ALTER TABLE legal_dossiers ENABLE ROW LEVEL SECURITY;
ALTER TABLE legal_dossiers FORCE ROW LEVEL SECURITY;
CREATE POLICY legal_dossiers_owner_isolation ON legal_dossiers
 USING (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid
    AND user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
    AND EXISTS (SELECT 1 FROM chat_conversations c WHERE c.id=legal_dossiers.conversation_id
      AND c.organization_id=legal_dossiers.organization_id AND c.user_id=legal_dossiers.user_id))
 WITH CHECK (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid
    AND user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
    AND EXISTS (SELECT 1 FROM chat_conversations c WHERE c.id=legal_dossiers.conversation_id
      AND c.organization_id=legal_dossiers.organization_id AND c.user_id=legal_dossiers.user_id));
GRANT SELECT, INSERT, UPDATE, DELETE ON legal_dossiers TO cfdt_juris_app;
COMMIT;
