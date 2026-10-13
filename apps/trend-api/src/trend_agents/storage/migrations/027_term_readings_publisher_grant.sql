-- 이미 등록된 게시 역할(publisher_db_roles)에 표제어 읽기(026) 읽기 권한을 준다. 게시 Job 은 캐시를 다시 만들며 이 표를 읽는데,
-- 역할 권한은 configure_publisher_role.py 를 다시 돌려야만 늘어난다 — 그 전 배포에서 게시가 권한 오류로 실패하지 않게(10-13).
-- 쓰기 권한은 주지 않는다. 역할이 아직 없으면(개발 DB) 아무것도 하지 않는다.
DO $grant$
DECLARE r record;
BEGIN
  FOR r IN SELECT p.role_name FROM publisher_db_roles p JOIN pg_roles g ON g.rolname = p.role_name LOOP
    EXECUTE format('GRANT SELECT ON term_readings TO %I', r.role_name);
  END LOOP;
END
$grant$;
