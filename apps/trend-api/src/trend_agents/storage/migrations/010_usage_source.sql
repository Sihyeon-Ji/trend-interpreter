-- 세대 줄의 출처(Plan 15). 옛 줄에는 출처가 없다 — 네이버 데이터랩 근거가 있는 표제어의 한국 줄은 실측(datalab), 나머지는 조사 모델의 추정(model).
ALTER TABLE usage ADD COLUMN IF NOT EXISTS source TEXT;
UPDATE usage SET source = CASE WHEN region = 'KR' AND term_id IN
  (SELECT DISTINCT term_id FROM evidences WHERE kind = 'datalab' AND source_domain = 'datalab.naver.com') THEN 'datalab' ELSE 'model' END
WHERE source IS NULL;
