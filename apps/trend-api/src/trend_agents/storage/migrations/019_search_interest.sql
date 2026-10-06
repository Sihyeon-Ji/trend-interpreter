-- 원본에 언급이 없어 생애주기를 정하지 못한 말(위키 밈 분류로 들어온 말 대부분, verified 의 91.7%)을 검색 관심도로 정한다(트윈 10-06).
-- 한국어는 네이버 데이터랩 주별 1년, 그 밖은 term_pageviews(월별). 값은 같이 부른 말끼리의 상대값이라 그 말 자신의 최고점 대비만 쓴다.
CREATE TABLE IF NOT EXISTS search_interest (term_id TEXT, source TEXT, period TEXT, value REAL, fetched_at TEXT, PRIMARY KEY(term_id, source, period));
