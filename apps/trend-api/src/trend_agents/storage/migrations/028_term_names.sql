-- 나라별 이름(10-13 사용자: "한국어에서는 비보, 일본어에서는 일본어"): 외국에서 온 말의 원어 이름. 그 화면 언어에서는 표제어 대신 이 이름을 크게 보인다
-- (규동 → 일본어 화면 牛丼, 고블린 모드 → 영어 화면 goblin mode). 수집 서버가 문서에 글자 그대로 있는 것만 넣어 스냅숏으로 들어온다.
-- headword 는 만들 때의 표제어 — 표제어가 바뀌면 옛 이름을 보이지 않는다. 게시 역할도 캐시를 다시 만들며 읽으므로 읽기 권한을 준다(027 과 같은 방식).
CREATE TABLE IF NOT EXISTS term_names (term_id TEXT, lang TEXT, headword TEXT, name TEXT, source TEXT, url TEXT, updated_at TEXT, PRIMARY KEY(term_id, lang));
DO $grant$
DECLARE r record;
BEGIN
  FOR r IN SELECT p.role_name FROM publisher_db_roles p JOIN pg_roles g ON g.rolname = p.role_name LOOP
    EXECUTE format('GRANT SELECT ON term_names TO %I', r.role_name);
  END LOOP;
END
$grant$;
