-- 용어마다 지난번 언급을 잰 나라(Plan 04). 돌아가며 재는 판의 다음 차례를 정한다 — 영어는 미국판에 더해 싱가포르·말레이시아·필리핀 영어판을
-- 하나씩. 중국어는 대만판에 더해 홍콩판도 잰다. 대만 뉴스판만 봐서 홍콩 키워드 검색이 0건이었다(2026-09-29).
ALTER TABLE mention_queries ADD COLUMN IF NOT EXISTS region TEXT;
-- 용어마다 뉴스 키워드 검색이 찾은 기사와 그 매체의 나라(Plan 04). 표제어의 나라 밖 판에서 받은 기사 가운데 근거가 아닌 것은 news 에 넣지 않고
-- 여기에만 둔다 — news 에 넣어 두면 같은 기사를 나중에 미국판에서 받아도 근거가 되지 못했다(검토 09-30).
CREATE TABLE IF NOT EXISTS mention_samples (term_id TEXT, region TEXT, link TEXT, source TEXT, home TEXT, published_at TEXT, PRIMARY KEY(term_id, region, link));
