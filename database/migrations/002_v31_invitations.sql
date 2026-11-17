BEGIN;
-- Replace the original tenant-only invitation policy with a narrow, one-token lookup
-- exception used only during authenticated invitation acceptance. All writes still
-- require the organization context established by the API after validating the token.
DROP POLICY IF EXISTS invitations_tenant_isolation ON invitations;
CREATE POLICY invitations_tenant_isolation ON invitations
 USING(
   organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid
   OR token_hash=NULLIF(current_setting('app.invitation_token_hash',true),'')
 )
 WITH CHECK(organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid);
COMMIT;
