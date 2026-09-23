# trend-agents

AI Builder Cup 2026 (Google Cloud JAPAC) 출전 프로젝트. 세대·문화 간 트렌드 통역 에이전트.
방향과 근거는 [docs/DIRECTION.md](docs/DIRECTION.md), 조사·실측은 [docs/research/](docs/research/).

## 구조

```
Google Cloud Hackathon.txt   대회 브리프 원본
docs/
  DIRECTION.md               방향성 (왜 이렇게, 무엇을 검증했나, 다음 단계)
  KEYS.md                    필요한 키·계정 체크리스트 (발급처·비용·시점)
  research/
    01-data-sources.md       데이터 소스 가능 여부·쿼터
    02-models-and-cost.md    Gemini/Gemma 선택, 비용
    03-feasibility-log.md    실제로 돌려본 것만 기록
    04-knowledge-graph-and-research-agents.md   사전(지식 그래프)·에이전트 루프·저장소 결정
src/trend_agents/
  config.py                  .env 로딩, 모델 ID, 대상 국가
  schemas.py                 공용 데이터 모델 (수집·해석 + 사전 계층)
  lifecycle.py               생애주기 판정 규칙 (판정은 데이터)
  verification.py            검증 게이트 규칙 (LLM 은 '검증됨'을 스스로 붙일 수 없다)
  collectors/                youtube · news_rss · naver_datalab
  interpreters/              gemini_video (쇼츠를 보고 해석) · gemini_research (grounding 조사) · gemma_local (로컬 분류·판정)
  storage/                   sqlite_store (수집 원본) · spanner_graph(.ddl.sql) (사전 지식 그래프)
  agents/                    ADK 에이전트 (예정)
scripts/                     단계별 실행 스크립트 (test_*.py) · export_schema.py (schemas.py → JSON Schema)
web/                         Next.js 프론트. 이용자: 메시지 해석 · 사전 / 관리자: /admin 검수 · 수집 현황. 한국어·영어. 예시 데이터 모드
  lib/contract/              schemas.py 에서 생성된 JSON Schema + TS 타입 (손으로 수정 금지)
  lib/sample/                예시 데이터 · lib/data.ts 데이터 접근 계층 · lib/check.ts 판정 규칙
  components/ app/           UI (design/Notion/DESIGN.md 토큰)
design/                      DESIGN.md (Notion) + 토큰 CSS
data/                        로컬 DB (git 제외)
```

## 실행

```bash
uv sync                       # Python 3.12 venv + 의존성
cp .env.example .env          # 키 채우기 (Gemini, YouTube, Naver)
ollama pull gemma4:12b        # 로컬 모델 (Ollama ≥ 0.34)
colima start && docker run -d --name spanner-emu -p 9010:9010 -p 9020:9020 gcr.io/cloud-spanner-emulator/emulator

# 키 불필요
uv run scripts/test_news_rss.py
uv run scripts/test_gemma_local.py
uv run scripts/test_dictionary_rules.py
uv run scripts/test_spanner_graph.py
# 키 필요
uv run scripts/test_youtube_collect.py            # YOUTUBE_API_KEY
uv run scripts/test_gemini_video.py [url ...]     # GEMINI_API_KEY
uv run scripts/test_naver_datalab.py [키워드]     # NAVER_CLIENT_ID/SECRET
```

## 프론트

```bash
cd web && pnpm install && pnpm dev        # http://localhost:3000 · 예시 데이터 모드
pnpm contract                             # schemas.py 변경 후 (루트에서 uv run scripts/export_schema.py 먼저)
```
화면·디자인 결정은 [docs/FRONTEND.md](docs/FRONTEND.md).

## 스택

Gemini 3.8 Flash (영상 해석 · Search grounding 조사) · Gemma 4 12B on Ollama (로컬 분류) · google-adk 2.x · Spanner Graph (사전 지식 그래프, GQL) · BigQuery (시계열 · GDELT) · YouTube Data API v3 · Google News RSS · 네이버 데이터랩 · Next.js 16 + Tailwind v4 + shadcn/ui (프론트) · Cloud Run (예정)

## 실행 (로컬)

```bash
cp .env.example .env            # 키 채우기 (docs/KEYS.md)
pnpm -C web dlx tsx scripts/export-sample.ts && uv run scripts/seed_dictionary.py   # 조사한 사전 52개 시드 (팀 확인 항목)
uv run scripts/run_pipeline.py  # 수집→분류→급증 조사→해석→후보→조사·검증→추세→네이버→언어판→보드, 1회
uv run scripts/serve_api.py     # API :8080
cd web && pnpm install && NEXT_PUBLIC_DATA_MODE=api pnpm dev   # 화면 :3000 (api 모드) — 기본은 예시 데이터 모드
uv run pytest -q
```

파이프라인 설계와 첫 실측은 [docs/PIPELINE.md](docs/PIPELINE.md), 화면은 [docs/FRONTEND.md](docs/FRONTEND.md), 출전 점검은 [docs/HACKATHON-CHECK.md](docs/HACKATHON-CHECK.md).
