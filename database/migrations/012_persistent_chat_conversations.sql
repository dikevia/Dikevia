BEGIN;
-- Conversations are private to one authenticated user inside one tenant.
CREATE TABLE chat_conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title text NOT NULL DEFAULT 'Nouvelle conversation' CHECK (char_length(title) BETWEEN 1 AND 160),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, id)
);
CREATE INDEX chat_conversations_owner_updated_idx
    ON chat_conversations(organization_id, user_id, updated_at DESC);

CREATE TABLE chat_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL CHECK (char_length(content) <= 50000),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, conversation_id)
        REFERENCES chat_conversations(organization_id, id) ON DELETE CASCADE
);
CREATE INDEX chat_messages_conversation_created_idx
    ON chat_messages(organization_id, conversation_id, created_at, id);

ALTER TABLE chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY;

CREATE POLICY chat_conversations_owner_isolation ON chat_conversations
    USING (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid
       AND user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
    WITH CHECK (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid
       AND user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
CREATE POLICY chat_messages_owner_isolation ON chat_messages
    USING (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid
       AND user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
       AND EXISTS (SELECT 1 FROM chat_conversations c WHERE c.id = chat_messages.conversation_id
          AND c.organization_id = chat_messages.organization_id
          AND c.user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid))
    WITH CHECK (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid
       AND user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
       AND EXISTS (SELECT 1 FROM chat_conversations c WHERE c.id = chat_messages.conversation_id
          AND c.organization_id = chat_messages.organization_id
          AND c.user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid));

GRANT SELECT, INSERT, UPDATE, DELETE ON chat_conversations TO cfdt_juris_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON chat_messages TO cfdt_juris_app;
COMMIT;
