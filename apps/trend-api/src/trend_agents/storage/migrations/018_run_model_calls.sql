-- 단계 실행마다 모델별 호출 수·걸린 시간(Plan 14 0단계: 관리 화면 '모델 기록'). runs.record_model 이 성공한 호출을 재고
-- runs.stage 가 실행 기록에 JSON 으로 남긴다({"local:gemma4:12b": [호출 수, 초]}). 잰 호출이 없으면 NULL.
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS model_calls TEXT;
