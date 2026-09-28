-- 확산 단계(Plan 02): 대시보드가 태동·확산·주류·식상으로 거르도록 열로 둔다. 값은 track 단계가 규칙으로 채운다.
ALTER TABLE terms ADD COLUMN IF NOT EXISTS diffusion TEXT;
UPDATE terms SET diffusion = json::jsonb ->> 'diffusion' WHERE diffusion IS NULL AND json::jsonb ? 'diffusion';
