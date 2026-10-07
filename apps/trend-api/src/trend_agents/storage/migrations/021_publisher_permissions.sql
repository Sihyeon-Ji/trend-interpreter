-- Database-level separation between review decisions and publication writes.
CREATE TABLE IF NOT EXISTS publisher_db_roles (role_name TEXT PRIMARY KEY);

CREATE FUNCTION guard_publisher_batch_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $body$
DECLARE restricted boolean;
BEGIN
  EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I.publisher_db_roles WHERE role_name=current_user)', TG_TABLE_SCHEMA)
    INTO restricted;
  IF restricted AND (
    (to_jsonb(NEW) - ARRAY['status','failure_code']) IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status','failure_code'])
    OR OLD.status NOT IN ('approved','failed')
    OR NEW.status NOT IN ('published','failed','conflict')
    OR OLD.reviewed_by IS NULL OR btrim(OLD.reviewed_by) = ''
  ) THEN
    RAISE EXCEPTION 'publisher_cannot_review_batches' USING ERRCODE='42501';
  END IF;
  RETURN NEW;
END;
$body$;

CREATE TRIGGER publisher_batch_update_guard BEFORE UPDATE ON change_batches
FOR EACH ROW EXECUTE FUNCTION guard_publisher_batch_update();
