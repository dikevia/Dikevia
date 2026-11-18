-- Temporary global beta capacity shared across all organizations.
-- Zero disables the cap; the temporary beta default is one shared account.
BEGIN;

CREATE OR REPLACE FUNCTION beta_user_slot_available(p_email text, p_max_users integer)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=public,pg_temp
SET row_security=off
AS $$
DECLARE
  normalized_email text := lower(trim(p_email));
  occupied_count bigint;
  already_reserved boolean;
BEGIN
  IF p_max_users = 0 THEN
    RETURN true;
  END IF;
  IF p_max_users < 0 OR p_max_users > 1000 OR normalized_email IS NULL OR normalized_email = '' THEN
    RAISE EXCEPTION 'invalid beta capacity arguments' USING ERRCODE='22023';
  END IF;

  -- Serialize invitation creation and acceptance so simultaneous requests
  -- cannot consume the same final slot.
  PERFORM pg_advisory_xact_lock(33010331);

  SELECT EXISTS (
    SELECT 1
    FROM memberships m
    JOIN users u ON u.id=m.user_id
    WHERE m.status='ACTIVE' AND u.status='ACTIVE'
      AND lower(u.email)=normalized_email
    UNION
    SELECT 1
    FROM platform_admins pa
    JOIN users u ON u.id=pa.user_id
    WHERE u.status='ACTIVE' AND lower(u.email)=normalized_email
    UNION
    SELECT 1
    FROM invitations i
    WHERE i.status='PENDING' AND i.expires_at>now()
      AND lower(i.email_normalized)=normalized_email
  ) INTO already_reserved;

  IF already_reserved THEN
    RETURN true;
  END IF;

  SELECT count(*) INTO occupied_count
  FROM (
    SELECT lower(u.email) AS email
    FROM memberships m
    JOIN users u ON u.id=m.user_id
    WHERE m.status='ACTIVE' AND u.status='ACTIVE'
    UNION
    SELECT lower(u.email) AS email
    FROM platform_admins pa
    JOIN users u ON u.id=pa.user_id
    WHERE u.status='ACTIVE'
    UNION
    SELECT lower(i.email_normalized) AS email
    FROM invitations i
    WHERE i.status='PENDING' AND i.expires_at>now()
  ) occupied;

  RETURN occupied_count < p_max_users;
END;
$$;

REVOKE ALL ON FUNCTION beta_user_slot_available(text,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION beta_user_slot_available(text,integer) TO cfdt_juris_app;

COMMIT;
