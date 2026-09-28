-- 나라별 원본 언급(Plan 04 완료 기준 "지역을 바꾸면 수치도 그 지역 데이터로만"). track 단계가 뉴스·쇼츠·검색어의 나라로 나눠 센다.
CREATE TABLE IF NOT EXISTS mentions_weekly_region (term_id TEXT, region TEXT, week_start TEXT, count BIGINT, PRIMARY KEY(term_id, region, week_start));
