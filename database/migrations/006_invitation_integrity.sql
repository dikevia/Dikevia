BEGIN;
-- Keep only the newest pending invitation for each organization/email pair.
-- Older duplicates are revoked rather than deleted so their audit trail remains intact.
WITH ranked AS (
  SELECT id, row_number() OVER (
    PARTITION BY organization_id, lower(email_normalized)
    ORDER BY created_at DESC, id DESC
  ) AS position
  FROM invitations
  WHERE status='PENDING'
)
UPDATE invitations i
SET status='REVOKED'
FROM ranked r
WHERE i.id=r.id AND r.position > 1;

CREATE UNIQUE INDEX IF NOT EXISTS invitations_one_pending_per_email_uq
  ON invitations(organization_id, lower(email_normalized))
  WHERE status='PENDING';
COMMIT;
