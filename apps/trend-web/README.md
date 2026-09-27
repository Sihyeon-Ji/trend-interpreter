# web — 트렌드 통역 프론트

Next.js 16 · Tailwind v4 · shadcn/ui · Pretendard. 디자인 토큰은 `../design/Notion/DESIGN.md`, 결정 기록은 `../docs/FRONTEND.md`.

```bash
pnpm install
pnpm dev                                  # http://localhost:3000 · 예시 데이터 모드
pnpm build && pnpm start -p 3100
pnpm contract                             # ../src/trend_agents/schemas.py → lib/contract/types.ts (루트에서 uv run scripts/export_schema.py 먼저)
```

| 경로 | 화면 |
|---|---|
| `/` | 메시지 해석 — 메시지를 붙이면 유행어·줄임말의 뜻을 설명 |
| `/dictionary` | 사전 (검색 · 세대·국가 필터) |
| `/dictionary/[termId]` | 항목 — 뜻 · 추세 · 출처 · 변경 기록 |
| `/admin`, `/admin/status` | 관리자 — 검수, 수집 현황 (푸터 링크) |

언어: 헤더에서 한국어 | English. 문구는 `lib/i18n.ts`, 유행어 원문은 번역하지 않음.

환경 변수는 `.env.example` 참고. `lib/contract/` 는 생성 파일이라 손으로 수정하지 않는다.
