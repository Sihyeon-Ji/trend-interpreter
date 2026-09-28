-- 별칭으로 용어를 찾을 때 모든 용어 JSON 을 훑지 않도록 별칭 표를 둔다. norm 은 파이썬 norm() 과 같은 규칙(공백 제거·소문자).
CREATE TABLE IF NOT EXISTS term_aliases (norm TEXT, term_id TEXT, PRIMARY KEY(norm, term_id));
INSERT INTO term_aliases (norm, term_id)
SELECT lower(regexp_replace(a, '\s', '', 'g')), term_id
FROM terms, jsonb_array_elements_text(json::jsonb -> 'aliases') AS a
ON CONFLICT DO NOTHING;
