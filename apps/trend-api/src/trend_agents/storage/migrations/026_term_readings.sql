-- 표제어 읽기(10-13 사용자 요청): 원문은 그대로 두고 다른 글자를 쓰는 화면에 작게 붙일 읽는 법 — 장원영 → 일본어 화면 チャン・ウォニョン, 영어 화면 Jang Won-young.
-- lang 은 읽는 사람의 화면 언어(ja 가타카나 · en 로마자 · ko 한글). 수집 서버가 만들어 규칙으로 거른 것만 스냅숏으로 들어온다.
-- headword 는 만들 때의 표제어 — 표제어가 바뀌면 화면이 옛 읽기를 내지 않는다(dictionary_store.get_readings).
CREATE TABLE IF NOT EXISTS term_readings (term_id TEXT, lang TEXT, headword TEXT, reading TEXT, source TEXT, updated_at TEXT, PRIMARY KEY(term_id, lang));
