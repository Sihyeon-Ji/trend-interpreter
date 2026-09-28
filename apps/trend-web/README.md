# web — 트렌드 통역 프론트

Next.js 16 · Tailwind v4 · shadcn/ui · Pretendard. 디자인 토큰은 비공개 디자인 문서(저장소에 넣지 않음), 결정 기록은 `../../docs/트렌드/프론트엔드.md`, 작업 규칙은 `../trend-api/AGENTS.md`.

평소에는 저장소 루트에서 `docker compose up -d` 로 API와 함께 띄운다(http://localhost:3000, 예시 데이터 모드).
호스트에서 직접 실행할 때는 다음을 쓴다.

```bash
corepack pnpm install --frozen-lockfile
corepack pnpm dev                         # http://localhost:3000 · 예시 데이터 모드
corepack pnpm build && corepack pnpm start
corepack pnpm contract                    # ../trend-api/src/trend_agents/schemas.py → lib/contract/types.ts (먼저 ../trend-api 에서 uv run scripts/export_schema.py)
```

실데이터 모드는 서버 환경변수 `DATA_MODE=api`와 `TREND_API_URL`로 켠다(`.env.example`). 두 값은 브라우저에 나가지 않는다.

| 경로 | 화면 |
|---|---|
| `/` | 메시지 해석 — 메시지를 붙이면 유행어·줄임말의 뜻을 설명 |
| `/dictionary` | 사전 (검색 · 세대·국가 필터) |
| `/dictionary/[termId]` | 항목 — 뜻 · 추세 · 출처 · 변경 기록 |
| `/admin`, `/admin/status` | 관리자 — 검수, 수집 현황 (푸터 링크) |

언어: 헤더에서 한국어 | English. 문구는 `lib/i18n.ts`, 유행어 원문은 번역하지 않음.

환경 변수는 `.env.example` 참고. `lib/contract/` 는 생성 파일이라 손으로 수정하지 않는다.
