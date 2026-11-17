BEGIN;
DROP FUNCTION IF EXISTS private_instance_set_member_status(uuid,uuid,uuid,text);
DROP FUNCTION IF EXISTS private_instance_pending_members(uuid);
ALTER TABLE memberships DROP CONSTRAINT IF EXISTS memberships_status_check;
ALTER TABLE memberships ADD CONSTRAINT memberships_status_check
  CHECK(status IN ('INVITED','ACTIVE','REVOKED'));
COMMIT;
