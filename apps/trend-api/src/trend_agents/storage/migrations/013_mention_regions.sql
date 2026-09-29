-- 용어마다 지난번 언급을 잰 나라(Plan 04). 여러 나라가 쓰는 말은 잴 때마다 돌아간다 — 중국어는 대만·홍콩을 번갈아,
-- 영어는 미국판에 더해 싱가포르·말레이시아·필리핀 영어판을 하나씩. 대만 뉴스판만 봐서 홍콩 키워드 검색이 0건이었다(2026-09-29).
ALTER TABLE mention_queries ADD COLUMN IF NOT EXISTS region TEXT;
