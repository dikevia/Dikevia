-- V3.43: append-only, tenant-scoped credit wallet foundation.
-- No monthly grants, purchases or AI debits are activated by this migration.
-- The debit procedure is available for a later cost-calibrated rollout only.
BEGIN;

CREATE TABLE credit_accounts (
    organization_id uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    balance bigint NOT NULL DEFAULT 0 CHECK (balance >= 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE credit_ledger_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    actor_user_id uuid NOT NULL REFERENCES users(id),
    entry_type varchar(32) NOT NULL CHECK (entry_type IN (
        'MONTHLY_ALLOCATION','PURCHASE','USAGE_DEBIT','EXPIRATION','ADJUSTMENT'
    )),
    delta bigint NOT NULL CHECK (delta <> 0),
    balance_after bigint NOT NULL CHECK (balance_after >= 0),
    idempotency_key varchar(128) NOT NULL CHECK (length(idempotency_key) BETWEEN 8 AND 128),
    reference varchar(160),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, idempotency_key)
);
CREATE INDEX credit_ledger_org_created_idx
    ON credit_ledger_entries(organization_id, created_at DESC, id DESC);

ALTER TABLE credit_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_accounts FORCE ROW LEVEL SECURITY;
CREATE POLICY credit_accounts_tenant_read ON credit_accounts
    FOR SELECT USING (
      organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid
    );

ALTER TABLE credit_ledger_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_ledger_entries FORCE ROW LEVEL SECURITY;
CREATE POLICY credit_ledger_tenant_read ON credit_ledger_entries
    FOR SELECT USING (
      organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid
    );

GRANT SELECT ON credit_accounts, credit_ledger_entries TO cfdt_juris_app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON credit_accounts, credit_ledger_entries FROM cfdt_juris_app;

-- The only write path is atomic: lock the tenant account, check idempotency,
-- reject an unaffordable debit, then update the balance and append the ledger
-- row in the same transaction. The tenant/user identity comes from RLS context.
CREATE OR REPLACE FUNCTION wallet_apply_entry(
    p_organization_id uuid,
    p_delta bigint,
    p_entry_type text,
    p_idempotency_key text,
    p_reference text DEFAULT NULL
) RETURNS TABLE(applied boolean, current_balance bigint, ledger_entry_id uuid)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
DECLARE
    v_user_id uuid;
    v_balance bigint;
    v_existing_id uuid;
BEGIN
    IF NULLIF(current_setting('app.current_org_id',true),'') IS NULL
       OR NULLIF(current_setting('app.current_org_id',true),'')::uuid <> p_organization_id THEN
        RAISE EXCEPTION 'tenant context required' USING ERRCODE='42501';
    END IF;
    IF NULLIF(current_setting('app.current_user_id',true),'') IS NULL THEN
        RAISE EXCEPTION 'user context required' USING ERRCODE='42501';
    END IF;
    v_user_id := NULLIF(current_setting('app.current_user_id',true),'')::uuid;

    IF p_delta = 0 OR p_entry_type NOT IN
       ('MONTHLY_ALLOCATION','PURCHASE','USAGE_DEBIT','EXPIRATION','ADJUSTMENT')
       OR (p_entry_type IN ('USAGE_DEBIT','EXPIRATION') AND p_delta > 0)
       OR length(COALESCE(p_idempotency_key,'')) NOT BETWEEN 8 AND 128
       OR length(COALESCE(p_reference,'')) > 160 THEN
        RAISE EXCEPTION 'invalid wallet entry' USING ERRCODE='22023';
    END IF;

    INSERT INTO credit_accounts(organization_id,balance)
      VALUES(p_organization_id,0) ON CONFLICT(organization_id) DO NOTHING;
    SELECT balance INTO v_balance FROM credit_accounts
      WHERE organization_id=p_organization_id FOR UPDATE;

    SELECT id INTO v_existing_id FROM credit_ledger_entries
      WHERE organization_id=p_organization_id AND idempotency_key=p_idempotency_key;
    IF v_existing_id IS NOT NULL THEN
      RETURN QUERY SELECT false,v_balance,v_existing_id;
      RETURN;
    END IF;

    IF v_balance + p_delta < 0 THEN
      RETURN QUERY SELECT false,v_balance,NULL::uuid;
      RETURN;
    END IF;

    v_balance := v_balance + p_delta;
    UPDATE credit_accounts SET balance=v_balance,updated_at=now()
      WHERE organization_id=p_organization_id;
    INSERT INTO credit_ledger_entries(
      organization_id,actor_user_id,entry_type,delta,balance_after,idempotency_key,reference
    ) VALUES (
      p_organization_id,v_user_id,p_entry_type,p_delta,v_balance,p_idempotency_key,NULLIF(p_reference,'')
    ) RETURNING id INTO v_existing_id;

    RETURN QUERY SELECT true,v_balance,v_existing_id;
END;
$$;

REVOKE ALL ON FUNCTION wallet_apply_entry(uuid,bigint,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION wallet_apply_entry(uuid,bigint,text,text,text) TO cfdt_juris_app;

COMMIT;
