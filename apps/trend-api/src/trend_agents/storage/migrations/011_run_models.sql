-- 단계 실행마다 부른 모델 ID(Plan 06 완료 기준 1: 로컬 편집 결과를 모델에 묶는다). pipeline/gemini.py 가 호출이 성공할 때 적고
-- runs.stage 가 실행 기록에 남긴다. 쉼표로 이어 두고(local:gemma4:e4b,gemini-3.5-flash), 모델을 부르지 않은 실행은 NULL.
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS models TEXT;
