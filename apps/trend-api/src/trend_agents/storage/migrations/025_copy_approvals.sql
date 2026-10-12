-- 문구 승인 기록(Plan 20 ⑤, ktwoo-copy-flow A1). 시장 하나의 초안 = 한 줄: 고른 밈·제품 한 줄·문구들·문구마다의 규칙 검사 결과·AI 의견,
-- 요청한 계정·시각, 결정(승인·반려)·결정한 사람·시각·메모. 이용자 문구는 이 표에만 둔다 – API 는 검수자·읽기 전용 계정에게만 본문을 보이고
-- 운영 로그·알림에는 쓰지 않는다. 본문(product·copies_json·fit_note)은 30일 뒤 지운다(storage/approvals.prune). 검사 결과 코드·사람·시각은 남는다.
-- 묶음(grp)은 규칙 검사 결과로만 정한다: blocked 쓰지 말라는 말·욕설 · read 규칙 표시나 AI 의견 '뜻과 다름'·판단 못 함 · clean.
CREATE TABLE IF NOT EXISTS copy_approvals (
  approval_id TEXT PRIMARY KEY,
  market TEXT NOT NULL,
  term_id TEXT NOT NULL,
  canonical TEXT NOT NULL,
  lang TEXT NOT NULL DEFAULT '',
  product TEXT,
  copies_json TEXT,
  checks_json TEXT NOT NULL,
  fit TEXT CHECK (fit IS NULL OR fit IN ('ok', 'off', 'unsure')),
  fit_copy BIGINT,
  fit_note TEXT,
  image_meme BIGINT NOT NULL DEFAULT 0,
  grp TEXT NOT NULL CHECK (grp IN ('blocked', 'read', 'clean')),
  reasons_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
  requested_by TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  decided_by TEXT,
  decided_at TEXT,
  memo TEXT,
  expired_at TEXT,
  CHECK (status = 'pending' OR (decided_by IS NOT NULL AND btrim(decided_by) <> '' AND decided_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS copy_approvals_status_at ON copy_approvals (status, requested_at);
