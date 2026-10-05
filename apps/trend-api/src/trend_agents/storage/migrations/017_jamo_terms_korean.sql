-- 한글 자모만 쓴 표제어(ㅋㅋ, ㅁㅊㄷ ㅁㅊㅇ)가 위키 분류의 지역·기본값을 따라 일본어·영어로 저장돼 있었다. 표제어 언어가 쓰는 나라를
-- 정하므로 한국 카피 검사에서 'ㅋㅋ' 가 이 시장에서 안 쓰는 말로 나왔다(2026-10-05). 새로 들어오는 말은 catalog.script_lang 이 막는다.
UPDATE terms SET lang = 'ko', json = jsonb_set(json::jsonb, '{lang}', '"ko"')::text
WHERE lang <> 'ko' AND canonical ~ '^[ㄱ-ㅎㅏ-ㅣ[:space:]]+$';
