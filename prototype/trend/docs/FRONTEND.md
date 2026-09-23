# 프론트 방향 (2026-09-14)

## 화면이 보여줘야 하는 것

| 화면 | 내용 | UI 요구 |
|---|---|---|
| 앞문 A · 카피 체커 | 카피 붙여넣기 → 세대 판정 → 리스크 플래그(근거 카드) → 리라이트 → 승인 → 발행 | 입력 패널, 판정 배지, 근거 카드(쇼츠 썸네일·출처·verified 칩), 승인 버튼, 발행 토스트 |
| 사전 항목 · 근거 뷰 | Term 헤더, 현행 뜻 + 버전 이력, 근거 목록, 생애주기 스파크라인, 세대×국가 확산 경로 | 속성 태그(세대·국가·카테고리·생애주기·검증), 타임라인, 표, 작은 차트 |
| 에이전트 활동 | 수집→분류→해석→발견→리서치→검증 단계별 건수, 검수 큐 | 상태 스트립, 큐 테이블 |
| 앞문 B · 메시지 통역(부가) | 메시지 → verified 뜻·출처·뉘앙스 인용 | 답변 카드 + 출처 카드 |

공통 제약: **한·일·태·아랍어 텍스트**가 본문에 섞인다. 라틴 전용 디스플레이 서체가 정체성인 시스템은 못 쓴다. 검증 상태와 생애주기를 색과 태그로 한눈에 읽혀야 한다. 심사 UX 배점은 10점이라 구현 속도가 우선.

## 선택: Notion DESIGN.md (1순위)

- 제품이 곧 "검증된 위키/사전"이고 Notion 은 데이터베이스 속성 태그(파스텔 색)를 시각 언어로 가진 시스템 → Term 의 세대·국가·카테고리·생애주기·검증 속성이 그대로 태그로 표현됨.
- 흰 캔버스 + 짙은 네이비 밴드 + 보라 필 CTA → 영상에서 읽기 쉽고, 네이비 밴드는 에이전트 상태 스트립으로, 보라 CTA 는 "승인·발행"으로 쓴다.
- 서체가 Inter 계열이라 **Pretendard Variable**(한국어) + Noto Sans JP/Thai/Arabic 폴백으로 바꿔도 인상이 유지됨.
- 일러스트(스티커 점, 와이어)는 빼고 그 자리에 쇼츠 썸네일·근거 카드를 넣는다.

대안:
- **Airtable** — 더 "데이터 제품" 느낌. 코랄·딥그린·피치·네이비 풀블리드 카드를 카테고리(유행어·밈·노래·뉴스) 색으로. 단 Haas Grotesk 는 교체.
- **Google Material 3** — 순수 Google 스택 서사와 구현 속도(컴포넌트 라이브러리) 최우선일 때. 칩·데이터 테이블·내비게이션 레일이 기본 제공. 대신 관리자 도구처럼 보일 위험.

피할 것: 다크 개발자툴 계열(Linear·Vercel·xAI·Composio — 한글 본문과 문화 콘텐츠에 안 맞음), 라틴 전용 디스플레이 서체가 정체성인 시스템(Stripe Sohne·Cal Sans·Verge Manuka·Nike Futura), 특정 브랜드 색 하나가 정체성인 시스템(Pinterest 빨강·Spotify 초록·Coinbase 파랑), Claude(크림·코랄 — Google 대회에서 Anthropic 룩), TikTok·YouTube(우리 데이터 소스라 모방으로 읽힘).

## 받은 파일 (design/)

- `design/Notion/DESIGN.md` — **본문 DESIGN.md** (색·서체·간격·모서리·컴포넌트·Do/Don't). 이게 기준.
- `design/Notion/{Tailwind.css, shadcn:ui.css}`, `design/Airtable/...` — DesignMD 토큰 내보내기. shadcn 변수(--primary 등)만 있고 파스텔 팔레트·서체는 없음. Airtable 은 전부 무채색이고 `.dark` 가 흰 배경으로 잘못 나옴 → Airtable 은 쓰지 않음.

## DESIGN.md → 우리 화면 대응표

| DESIGN.md 요소 | 우리 제품에서 |
|---|---|
| `hero-band-dark` (brand-navy) | 상단 **에이전트 파이프라인 상태 스트립**(수집→분류→해석→발견→리서치→검증 건수). 스티커 점 장식은 각 단계 색점으로 |
| `workspace-mockup-card` (Level 3 그림자) | 카피 체커의 **판정 결과 패널**, 사전 항목의 **현행 뜻 카드** |
| `card-base` / `card-agent-tile` | 근거 카드(EvidenceCard), 에이전트 타일 |
| `card-feature-*` 파스텔 틴트 | **카테고리 블록**: slang=lavender · meme=rose · song=sky · drama=peach · dance=yellow · news=gray · geopolitics=navy-mid(on-dark) · product=mint · other=cream |
| `badge-tag-*` (틴트 배경 + 진한 글자, rounded.sm) | **속성 태그**: 세대·국가·카테고리 |
| `badge-tag-green` mint / `card-tint-sky` / `card-tint-yellow-bold` / `card-tint-gray` / `badge-tag-orange` peach / `card-tint-cream` | **생애주기 태그**: emerging=mint+brand-green · rising=sky+link-blue-pressed · peak=yellow-bold+charcoal · steady=gray+slate · declining=peach+brand-orange-deep · dormant=cream+stone |
| `badge-tag-purple` lavender / sky / yellow / rose | **검증 태그**: verified_human=lavender+purple-800 · verified_auto=sky+link-blue-pressed · unverified=yellow+brand-brown · rejected=rose+brand-pink-deep |
| `badge-purple` (solid, full) | "verified" 최종 도장, 승인 완료 |
| `button-primary` (purple, **8px 직사각형**) | **승인·발행** 단 하나 |
| `button-secondary` / `button-ghost` | 리라이트 다시, 검수 보류, 취소 |
| `button-link` (link-blue) | 출처 URL, 영상 링크 — 보라와 절대 혼용 금지 |
| `text-input` 44px, focus 2px purple | 카피 입력, 메시지 입력 |
| `pill-tab` / `pill-tab-active` (ink-deep) | 필터: 세대 · 국가 |
| `segmented-tab` (밑줄) | 사전 항목 탭: 뜻 · 근거 · 이력 · 확산 |
| `comparison-table` / `comparison-row` | 검수 큐 테이블, 버전 이력 표 |
| `stat-row` (surface) | 생애주기 스파크라인 + 숫자 스트립 |
| `promo-banner` | "조용한 0" 경보, 키 미설정 안내 |
| Elevation 0 (hairline) | 기본. 문서형 카드에 무거운 그림자 금지 |

## 규칙 중 우리가 지킬 것 / 바꿀 것

- 지킴: 버튼 8px 직사각형(필 금지), 카드 12px, 태그만 full/sm, 보라는 CTA 전용(본문·넓은 면 금지), link-blue 와 보라 역할 분리, 1280px 컨테이너 + 32px 거터, 8px 간격 리듬, 라이트 모드만(다크 토큰이 문서에 없음).
- 바꿈: 서체. Notion Sans 는 못 쓰고 문서는 "generic Inter 로 대체 금지"라 하지만 한·일·태·아랍 본문이 필수 → **Pretendard Variable**(라틴 부분이 Inter 기반이라 인상 유지) + Noto Sans JP/Thai/Arabic 폴백. 타이포 스케일(80/56/48/36/28/22/18/16/14/13/12)과 굵기(600 제목·500 버튼·400 본문)는 그대로.
- 추가: 위 생애주기·검증·카테고리 의미 색을 `@theme` 토큰으로 정의(전부 DESIGN.md 팔레트 안에서만 고름).

## 컴포넌트 목록

StatusTag(lifecycle·verification·category), EvidenceCard, VersionTimeline, Sparkline, ReviewQueueTable, ApprovePublishButton, AnswerCard(출처 카드 포함), PipelineStatusStrip, CategoryBlock.

## 스택 (안)

Next.js + Tailwind + shadcn/ui 를 DESIGN.md 토큰으로 테마 → Cloud Run(또는 Firebase Hosting) 배포. API 는 기존 Python(ADK) 서비스. 차트는 가벼운 것 하나(recharts 급)만.


---

## 구현 현황 (2026-09-14 16:10 · 2차)

1차(대시보드형)를 사용자 피드백으로 전면 수정했다. 피드백: "AI 도구 티가 난다", "검수 큐는 관리자 화면에", "카피 판정이 아니라 메시지를 넣으면 무슨 뜻인지 설명해 주는 것", "전문 용어를 이용자에게 보이지 말 것", "한국어·영어 전환".

### 화면 (이용자 / 관리자 분리)

| 구분 | 경로 | 내용 |
|---|---|---|
| 이용자 | `/` 메시지 해석 | 메시지 붙여 넣기 → 설명 보기. 표현별로 뜻 한 줄 → 유래·뉘앙스·누가 쓰나 문단 → 출처 1건 → 사전 링크. 맨 위에 "쉽게 풀어 쓰면"(쉬운 표현으로 치환한 문장) |
| 이용자 | `/dictionary` | 검색 + 세대·국가 셀렉트 + 표 형태 목록 |
| 이용자 | `/dictionary/[id]` | 뜻 → 추세(문장 + 무채색 스파크라인 + 어디서·처음 언급·비중 표) → 출처 → 변경 기록 |
| 관리자 | `/admin` 검수 | 자동 확인이 안 된 제안: 제안된 뜻 · 확인이 필요한 이유 · 승인/보류/제외 |
| 관리자 | `/admin/status` 수집 현황 | 단계별 24시간 건수 표 |

관리자 화면은 메인 내비에 없고 푸터 "관리" 링크로만 간다. 이용자 화면에는 확인 사유·자동 조사·판 수·확신도 같은 내부 정보를 내지 않는다.

### 디자인 등록부 (Notion DESIGN.md 의 '앱' 쪽만)

- 흰 바탕, 검정/차콜/스틸 글자, hairline. 색은 링크 파랑과 "주의" 표기용 빨강만. 파스텔 틴트·네이비 밴드·보라 CTA·카드 그림자·글리프(↗✓▲)·큰 마케팅 제목은 전부 제거.
- primary 버튼 = `button-dark`(검정). 카드 대신 구분선 목록. 컨테이너 960px.
- 서체 Pretendard Variable, `word-break: keep-all`.
- 이유: 사용자 요구("호불호 없는", "섹터 구분 없는")와 artifact-design 스킬의 AI 디자인 클러스터 경고(파스텔 태그·라운드 카드·색 띠·글리프·중앙 정렬 히어로)가 일치.

### 이용자 관점 점검에서 고친 것

예시 메시지를 광고 카피 → 자녀가 부모에게 보낸 카톡 문장으로. 설명 4문장 한 덩어리 → 뜻 한 줄 + 배경 문단. 출처와 사전 링크 줄 분리. "관측" → "언급". 확인 주기 문구는 관리 화면으로. 내비 "해석" → "메시지 해석". 관리 표 머리글 줄바꿈 방지. 모바일 헤더가 한 줄에 몰려 글자가 꺾이던 것 → 폰에서는 메뉴를 둘째 줄로.

### 언어 (한국어 · 영어)

- **화면 문구**: `web/lib/i18n.ts` 사전식 고정 번역. `t(locale, key)`. 키가 빠지면 타입 에러.
- **데이터 라벨**(세대·국가·추세·카테고리·출처 종류): `web/lib/labels.ts` 의 `L(locale)`.
- **유행어 원문은 절대 번역하지 않는다.** 뜻·유래·뉘앙스·쉬운 표현만 언어별로 둔다 → 계약 `MeaningText` (schemas.py 추가, TS 재생성).
- **번역 생산**: 백엔드 로컬 Gemma (`interpreters/gemma_translate.py`). 저장 시점에 언어별로 만들어 두고 요청마다 돌리지 않는다. 실측(`scripts/test_gemma_translate.py`, gemma4:12b): 한→영 8~13초, 영→한 7~9초, 용어 원문(자만추·인만추) 보존. 프롬프트 수정 후 한→영에서 줄임말 풀이(expansion) 유지 확인. 영→한 역번역에서는 풀이가 null 로 빠짐 — 원문 언어로 되돌리는 경우는 실제 용도가 아니므로 보류.
- **언어 선택**: 쿠키 `locale` (헤더 한국어 | English). 서버 컴포넌트가 `getLocale()` 로 읽어 렌더 → 전 페이지 동적 렌더링.
- 예시 데이터에는 10개 항목 전부 영어판(`TermRecord.en`)과 영어 예시 메시지가 들어 있다.
- 변경 기록은 원문(한국어) 기준. 영어 화면에서는 그 사실을 한 줄로 알린다.

### '쉽게 풀어 쓰면' 은 모델 재작성 (규칙 치환 폐기)

사용자 지적: 단어 치환("완전 오히려 좋아잖아?", "긍정적으로 생각하기 가자")은 어색하다. → 로컬 Gemma 가 사전의 **뜻 문장**을 참고해 메시지 전체를 다시 쓴다 (`interpreters/gemma_rewrite.py`). 뜻 판단은 사전이, 문장만 모델이.

실측 (`scripts/test_gemma_rewrite.py`, gemma4:12b, 3~11초, 두 번 실행 결과 동일):

| 프롬프트 | 결과 |
|---|---|
| v1 (짧은 쉬운 말 목록만 제공) | 단어를 그대로 끼워 넣음. 영어는 감탄사를 빼며 문장이 잘림("bro is so") |
| v2 (뜻 문장 + 나쁜 예/좋은 예 + 예시 한 쌍 + "문장이 완결되게") | 엄마 오늘 저녁 메뉴 좀 추천해줘ㅋㅋ 소개팅은 됐고 나는 자연스럽게 만나서 연애할래. 시험은 망했는데 오히려 운이 좋네? 긍정적으로 생각하자 / ngl that boat kid is just trying to look impressive on purpose 😭 bro is so silly |

프론트: `web/lib/explain.ts` 에서 규칙 치환을 지웠다. 해석은 `POST /api/explain`(Next route) → `lib/data.ts explain()` 으로 간다. 샘플 모드는 로컬 매칭 + 예시 메시지에 대해 미리 생성한 재작성(`SAMPLE_REWRITES`)만 보여주고, 다른 메시지는 재작성 없이 항목 설명만 낸다. api 모드는 Python `/explain` 이 매칭 + Gemma 재작성을 돌려준다.

### 데이터 흐름

```
schemas.py ──(uv run scripts/export_schema.py)──▶ web/lib/contract/schema.json ──(pnpm -C web contract)──▶ web/lib/contract/types.ts
web/lib/types.ts       계약 재수출 + 뷰 모델 (TermRecord{…, en?: MeaningText}, PipelineStage, ReviewItem)
web/lib/sample/        예시 데이터 · web/lib/data.ts 데이터 접근 계층 · web/lib/explain.ts 해석 조립(규칙)
```

### 계약 갭 (백엔드에 반영할 것)

- `Term.category` 없음 (뷰 모델에만). `Meaning.translations: dict[lang, MeaningText]` 컬럼 필요 (Spanner DDL). `plain`(쉬운 표현)은 Meaning/MeaningText 로.
- API 응답 형태: `/terms`, `/terms/{id}` → `TermRecord`, `/pipeline/stages` → `PipelineStage[]`, `/review/queue` → `ReviewItem[]`, `POST /explain {text, lang}` → `ExplainResult{items, plain}` (plain = Gemma 재작성, 캐시 권장). 언어는 `Accept-Language` 또는 `?lang=`.
- 사전에 없는 표현이 들어오면 자동 조사 큐에 넣는 API — 지금 화면은 "새 표현은 확인을 거쳐 사전에 추가됩니다" 문구만.

### 심사 기준 대응 메모

B2B 카피 판정 흐름을 뺐으므로 "실행 단계 + 사람 승인"은 관리자 검수(승인 → 사전 게시)가 담당한다. 이용자 화면은 조회·설명이지만, 그 뒤에 수집·해석·조사·확인 에이전트와 검수 승인이 있다는 것을 덱·영상에서 관리 화면으로 보여준다.

### 실행

```bash
cd web && pnpm install
pnpm dev                                   # http://localhost:3000 (예시 데이터)
pnpm build && pnpm start -p 3100           # 재시작 전: lsof -ti :3100 | xargs kill
pnpm contract                              # schemas.py 변경 후 (루트에서 uv run scripts/export_schema.py 먼저)
uv run scripts/test_gemma_translate.py     # 로컬 번역 실측 (루트, Ollama 필요)
```


---

## 3차 (2026-09-14 16:40) · 사전 확장 + 사용 테스트

### 추가한 한국 유행어 20개 (`web/lib/sample/korean-2026.ts`)

웹 조사(나무위키·경향신문·매일경제·캐릿·여행픽·네이트 카드뉴스·카더라 상반기 결산·하퍼스바자) 기준. 뜻·유래는 조사 결과, 언급 수·비중은 가정치.

| 용어 | 요지 | 추세 |
|---|---|---|
| 영크크 · 늙크크 | 2026-02 CORTIS 'YOUNGCREATORCREW' 가사에서. 젊은 감각 / 아재 감성. 2030 자조 | 꾸준히 |
| 밤티 · 중티 | 촌스럽다·엉성하다 / '중국 티 난다'. 라인플레이 닉네임 → 2025 X 재유행. 실존 인물 닉네임·국적 비하 주의 | 늘어나는 중 |
| 야르 · 샤갈 · 아자스 | 감탄사 3종 (신남 / 욕설 완곡어 / 일본어 감사 축약) | 정점·꾸준히 |
| 난리자베스 | 크리에이터가 "배포"해 성공한 유행어. [감정]+자베스 | 줄어드는 중 |
| 테무인간 · 젬민이 · AI slop(슬롭) | 사람 유형·AI 관련 | 꾸준히·늘어나는 중 |
| 테토남(에겐) | 2025 성격 유형 밈 | 줄어드는 중 |
| 윤정아 챌린지 · 나무 챌린지 | 2026 상반기 최대 밈 2종 | 줄어드는 중 |
| 두쫀쿠 | 2025 하반기 히트 간식 | 줄어드는 중 |
| 추구미 · 느좋 · 점메추 · 반 오십 | 생활 유행어 | 꾸준히 |
| Tung Tung Tung Sahur | 이탈리안 브레인로트 대표 | 줄어드는 중 |

기존 데이터 오류 수정: 점메추(점심)가 저메추(저녁)의 다른 표기로 들어가 있던 것을 별도 항목으로 분리.

### 사용 테스트 (`web/scripts/explain-check.mjs`, 29 케이스, 서버 필요)

조사·어미 붙음, 띄어쓰기 없음, 별칭·활용형·파생형, 반복, 영·일·한 혼용, 대소문자, 숫자, 유행어 없음, 사전에 없는 말 등. **29/29 의도대로.** 이 과정에서 고친 것:

- 영문·숫자 용어는 단어 경계 필수: "6-7" 이 "2026년 6 7월", "010-6-7-1234", "Skibidiman" 에 걸리던 것 수정 (`termPattern`).
- 한국어 용어는 띄어쓰기 변형 허용("원영적사고").
- 영어 설명 "people in their all ages" → "Used across all ages."; 합성어("Lucky + Vicky")를 '줄임말'이라 부르던 문장 → "…에서 온 말입니다 / From …"; 영어 풀이의 따옴표 중첩 정리.
- 사전 목록: 언어 필터 추가, 화면 언어의 용어를 먼저 보이고 가나다·ABC 정렬(영어권 이용자는 한국어 용어를 섞어 쓰지 않는다는 전제). 영어 예시 메시지는 영어 유행어만.

**남는 한계 (사전만으로는 못 가름, 모델 단계가 맡을 것):** 화가 '샤갈' vs 감탄사 샤갈, "rated 6-7 out of 10" 의 숫자 범위 vs 밈. 이용자 화면에서는 두 뜻이 다 나올 수 있다는 점을 감안해 확신 표현을 쓰지 않는다.


---

## 4차 (2026-09-14 19:00) · 최신 밈 추가 — "다 너무 옛날 거"

사용자가 캐릿 '요즘 뜨는 밈' 시리즈와 나무위키 밈/시기별 2026 목록을 주며 최신 것을 넣으라고 함. 캐릿 글은 앞부분만 공개(약 25~30%)라 보이는 항목만 쓰고, 가려진 것은 다른 출처로 확인했다. 22개 추가 (`web/lib/sample/latest-2026.ts`) → 사전 52개.

| 구분 | 용어 | 근거 요약 |
|---|---|---|
| 한국 8월 | 삐에로 밈(선배삐·개대박삐·삐바삐·삐출) | 2026-08-13 더쿠 결혼 고민글 → 캐릿 08-25, 인사이트, 다음뉴스 08-29, 고구마팜 |
| 한국 8월 | 또 가고 싶은 OO입니다 | 캐릿 08-12 (공간 탐닉·더들리) |
| 한국 8월 | 속담 오타 밈(모르는 개 산책 등 4종) | 캐릿 08-12 |
| 한국 7월 | 책없쾌 · 오살힘 · 무공해 | 캐릿 07-08 + 인스타공백닷컴·인스티즈·Dcard(대만)·엘르 |
| 한국 4~6월 | 야르송 · 천연 위고비 · 자려고 누웠는데 양의지 · 라을라 · 백룸코어 | 유괴된돌고래 원곡·온밈·TV조선 / 위키트리·인스타공백 / YTN·MBC·KBOPLAYLIST / 인스타공백·더쿠 / 캐릿 06-17·KYM |
| 글로벌 6~9월 | Ronaldo Pasta · Three Layer Dip Stack · La Peace · Ptpa Ptpe Ptpi Ptpo Ptpu · Argentina AI Muscle Dancing · viral Crumbl Labubu cookie · Du Bist Gut Genug · Remember November 2026 Is Coming · Wow okay · I forgot my AirPods | Know Your Meme·Yahoo/KYM 해설·meme.com·giga.de·틱톡 원본 |
| 확인 중 | 사보필 | 캐릿 07-08 목차에만 존재, 뜻은 유료 구간 → `needs_review` + 검수 큐 |

넣지 않은 것: 나무위키 목록의 Verity · MECCHA CHAMELEON · Folk Valley · 牛来 · He Took a Bite of a Boneless Wing · What's Your Favourite Cereal 등 — 뜻·유래를 확인할 출처가 없었다. 멜라토닌 먹고 꾸는 꿈 같다, 번복 밈, 오디세이 밈도 같은 이유.

### 배터리 테스트 47 케이스 → 47/47

추가 케이스에서 잡은 것: 정의 문장 첫머리에 '…의 줄임말.'을 넣으면 설명문에서 "'…'의 줄임말입니다. '…'의 줄임말." 로 두 번 나온다 → 정의에서 풀이 반복 제거(데이터 규칙: definition 은 expansion 을 되풀이하지 않는다). "또 가고 싶은" 처럼 평범한 어구가 밈 포맷인 경우는 별칭을 "지만 또 가고 싶은" 식으로 좁혀 오탐을 막았다. 새 한계: 환경 용어 '무공해 자동차'와 사람 평가 '무공해'는 사전만으로 못 가른다(모델 단계).


---

## 5차 (2026-09-14 22:30) · 지도 — 사전을 품는 큰 틀

사용자 비전(09-14 21:36): "사전은 부품. 큰 틀은 구글 지도/어스 같은 세계 지도. 나라별로 뜨는 키워드가 말풍선으로 뜨고, 누르면 목록·추세. 오징어 게임처럼 한 트렌드가 나라를 건너가며 현지 밈으로 이어지는 흐름이 지도에 보여야 한다. 애니메이션·모션이 가장 중요." + "나라 × 카테고리 표". Gemma 는 램 부족으로 보류, 결제는 필요할 때.

### 결정

- **키 없는 벡터 지도** (`d3-geo` + `world-atlas` 110m + `d3-zoom`). Google Maps JS API 는 결제 계정 없이는 켜지지 않는다 → 나중에 결제를 붙이면 타일 배경만 바꿀 수 있게 지도 로직을 컴포넌트 하나(`components/trend-map.tsx`)에 가둠.
- **투영은 140°E 중심** Natural Earth. 대회가 JAPAC 이라 아시아·태평양이 가운데, 대서양 한가운데서 끊긴다.
- **말풍선**: 나라 중심점 + 손으로 정한 오프셋(`OFFSET`, 바다 쪽으로) + 지시선. 기본 배율에서는 항목 많은 10개 나라만, 1.6배 이상 확대하면 전부(`LOD_*`). 확대해도 글자 크기는 역보정(`scale(1/k)`).
- **전파 경로**: 출발점 맥동 링 + 화면 좌표에서 위로 굽은 곡선을 순서대로 그림(`stroke-dashoffset` 애니메이션, 도착 점·이름표는 0.55초 간격으로 등장). 대권(great circle)은 날짜변경선에서 끊기고 북극 위로 돌아가 읽기 어려워서 화면 곡선으로 바꿈. 경로 아래에는 날짜·나라·현지 이름·한 줄 설명 타임라인.
- **패널**: 넓은 화면은 지도 위 오른쪽에 겹치는 카드, 좁은 화면은 지도 아래. 항목마다 순위·원문·미니 추세선·한 줄 설명·변화(새로 등장/상승/하락/유지)·'퍼진 경로'·'사전에서 보기'.
- **딥링크** `/map?region=KR&cluster=c_squid` — 데모·공유용.
- **모션 규칙**: 말풍선은 안쪽 `<g>` 만 CSS 로 움직인다(바깥 `<g>` 의 transform 속성을 CSS 가 덮어쓰면 위치가 날아간다). `prefers-reduced-motion` 이면 전부 정지.
- **좁은 화면**: 지도는 최소 720px 로 가로 스크롤, 처음에 아시아가 보이게 가운데로 스크롤. 표는 `overflow-x-auto`.
- 디자인 등록부 유지: 흰 바탕, 회색 육지 3단(#f2f2f2 / 자료 있음 #e2e2e2 / 경로 포함 #cdcdcd), 선택 나라만 검정, 카테고리별 색 없음.

### 데이터

- 뷰 모델 `web/lib/trends/types.ts` (`TrendItem`, `TrendCluster`, `TrendBoard`) — **계약(schemas.py) 미반영**. 백엔드 `TrendQuery`(Google Trends 수집) → 분류 → 사전 매칭 → 보드로 만드는 단계가 다음 일.
- 예시 `web/lib/sample/trend-board.ts`: 14개 나라 × 7 카테고리 74항목. 검색어·영상 제목은 09-14 실측(BigQuery·RSS·YouTube)에서, 패션·뷔티와 몇 항목은 '(가정)' 표시. 전파 7개: 오징어 게임(사용자 예시, 브라질 제목 'Round 6' 실제), 6-7, Tung Tung Tung Sahur, 두쫀쿠→Korean chewy cookie(실제 연결), Du Bist Gut Genug, aura farming, Ronaldo Pasta.
- 카테고리 7개: 유행어·밈 / 노래·챌린지 / 패션·뷔티 / 음식 / 제품 / 인물·콘텐츠 / 스포츠·이벤트 (`labels.trendCategory`).

### 검증

tsc·lint·build 통과, 해석 배터리 47/47 유지, 스크린샷 1280(기본·한국 패널·오징어 게임 경로·Tung Tung 경로)·400(가로 스크롤) 확인. 잡은 것: 대서양 중심 투영에서 아시아 말풍선 잘림 → 140°E 회전; 옆 패널로 지도가 절반 → 겹치는 패널; 브라질 말풍선 우측 잘림 → 안쪽 오프셋; 경로 이름표 겹침 → 말풍선 오프셋 재사용.


---

## 6차 (2026-09-14 23:30) · 3D 지구 + 나라별 차이 — 5차 전면 재작업

사용자 피드백(21:59): "너무 별로. 지도를 제일 크게, 3D 로. 사이드탭이 열리는 게 보이지 않는다. 같은 키워드가 나라별로 어떻게 다른지가 없다 — 오징어 게임이면 한국은 '기훈이 형' 대사 밈, 미국은 MrBeast 처럼 자기들 유행과 엮여야 한다. 프론트 디자인 스킬 로드, 섹터 구분 없는 호불호 없는 대기업식 UI/UX, AI 디자인 특징 금지, 사용자 관점, 캡처 필수."

### 무엇이 바뀌었나

- **정보 구조**: '나라를 건너간 트렌드'(`TrendCluster` = 화살표 목록)를 **주제(`Topic`) + 나라별 변형(`TopicVariant`)**으로 바꿈. 변형마다 현지 이름·처음 시점·관심도·**무엇이 달라졌나 한 줄·현지 밈·놀이·엮인 현지 트렌드**를 갖는다. 오징어 게임 예: 한국 '기훈이 형 대사 밈·무궁화·달고나', 미국 'MrBeast 실사판·Red Light Green Light·Beast Games', 브라질 'Round 6·Batatinha frita 1,2,3', 일본 'だるまさんがころんだ 비교·型抜き', 대만 '一二三木頭人·椪糖', 인도 '힌디 더빙 대사 밈'. 주제 9개(오징어 게임·6-7·Tung Tung Tung Sahur·두쫀쿠·라부부·두바이 초콜릿·Du Bist Gut Genug·aura farming·Ronaldo Pasta), 데이터 `web/lib/sample/trend-board.ts`.
- **화면**: `/map` 전폭. 왼쪽 400px 고정 패널(항상 보임: 검색 → 나라를 건너간 트렌드 목록 → 나라별 목록; 누르면 같은 패널에서 상세로, '뒤로'), 오른쫀 **3D 지구(globe.gl)**가 뷰포트를 채움. 그 아래 **'나라별 차이' 비교표**(주제 탭 · 나라/현지 이름/처음/관심도/무엇이 달라졌나/현지 밈/엮인 트렌드) + 나라 × 카테고리 표.
- **지구**: 흰 배경 위 무광 회색 구(`#f4f6f8`), 육지 3단 회색(자료 없음/있음/주제 포함) + 선택 검정, 국경 흰 선. 나라별 말풍선(나라명 + 1위 항목 + N)은 HTML 요소로 지구에 붙어 가려지면 사라짐. **경로**: 주제를 열면 1.3초 간격으로 한 나라씩 호가 그려지고(점선 흐름) 출발점은 맥동 링, **카메라가 출발점과 그 나라가 함께 보이는 구면 중점으로 따라간다**. 좁은 화면은 멀리서 시작하고 말풍선 6개만.
- **라이브러리**: `globe.gl` 2.46(three 포함). 화면에서만 `import()` — SSR 금지. Google Maps/Earth 는 결제 필요 → 보류 유지.
- **레이아웃 리팩터**: 루트 레이아웃의 960 컨테이너를 `components/page-shell.tsx` 로 내려 일반 페이지가 각자 감싼다. 상단 바·푸터는 전폭(앱 바).
- **디자인 등록부**: DESIGN.md 앱 쪽 그대로. 색은 회색 단계와 검정만, 카테고리 색 없음, 카드 그림자·그라디언트·이모지 없음. 아이콘은 lucide 4종(검색·뒤로·확대·축소·처음·회전).

### 잡은 것

- globe.gl 의 HTML 레이어(CSS2DRenderer)는 요소의 `transform` 을 매 프레임 덮어쓴다 → 말풍선 오프셋이 지워짐. **0×0 기준점 요소 안에 말풍선을 넣고 그 안에서만 비켜 놓는다**(`.globe-anchor` > `.globe-bubble` + 지시선).
- 대권 호를 카메라 반대편으로 그리면 지구 위에 조각처럼 떠 보인다 → 호 높이 0.16 로 낮추고 카메라가 따라가게.
- 모바일에서 `flex-1` 이 지구 영역을 900px 로 키움 → 고정 `54vh`.
- React Compiler lint: 렌더 중 ref 접근(배열 안의 핸들러는 핸들러로 인식 안 됨 → 인라인 onClick), 효과 안 동기 setState(타이머로), `Date.now()`(카운터로).
- 캡처: `docs/screenshots/2026-09-14-globe-{home,squid-route,korea,phone,full}.png`.

### 남은 것

- `Topic/TopicVariant` 를 `schemas.py` 계약에 반영하고, Google Trends 검색어 → 카테고리 분류(Gemini 텍스트) → 사전 매칭 → 보드 API(`/trends/board`).
- 말풍선 오프셋은 손으로 정한 값(`BUBBLE_OFFSET`). 나라가 늘면 자동 배치가 필요.
- 첫 화면을 지도로 바꿀지는 사용자 결정 대기.


---

## 7차 (2026-09-14 23:15) · api 모드 연결

- `lib/data.ts` api 모드: `/explain` 은 `{term_ids, plain}` 만 받고 문장 조립은 `lib/explain.ts` 가 화면 언어로 한다(백엔드와 로직 중복 없음). 목록·상세·검수·상태·보드는 FastAPI 응답을 그대로 쓴다(`pipeline/views.py` 가 `lib/types.ts` 와 1:1).
- api 모드 확인: `NEXT_PUBLIC_DATA_MODE=api NEXT_PUBLIC_API_BASE=http://localhost:8080 pnpm dev -p 3200` → 5개 화면 200, `/admin/status` 에 실제 단계 건수. 상태 표 셀 줄바꿈 수정, 예시 문구("마지막 실행 06:00") 제거.
- 지구: 주제가 없으면 '나라를 건너간 트렌드' 절과 비교표를 숨긴다(실데이터 초기 상태).
- 배포: `web/Dockerfile`(standalone) — `NEXT_PUBLIC_*` 는 빌드 인자.


---

## 8차 (2026-09-15 11:10) · 뒤에서 하는 일을 화면으로 — 실데이터 모드 전환

사용자 지적: "백엔드 수집은 많은데 프론트는 보여 주는 게 없다." 원칙(이용자에게 내부 용어 금지)을 지키며 백엔드 결과를 이용자 가치로 바꿈.

- **3100 을 api 모드로**(`NEXT_PUBLIC_DATA_MODE=api`). `lib/data.ts` 는 API 우선·실패 시 예시 폴백(`apiOr`). 지구·사전에 "마지막 갱신 시각"(`/meta`).
- **왜 지금 뜨나 카드**(`components/why-card.tsx`): 지구 나라 패널과 나라 페이지. 두 문장 설명, 계기(인플루언서·출시·사건·논란·밈·홍보·명절·경기), 관련 인물, 첫 신호 날짜, 근거를 종류별 개수로 접어 둠 → 펼치면 링크 목록. 데이터: `TrendBoard.why` (백엔드 `board.why_list`, 급증 근거는 `evidences` 에 `q|검색어|나라` 키로 저장).
- **용어 페이지**: '포착에서 확인까지' 타임라인(`term-timeline.tsx`: 처음 포착 → 첫 근거 → 뜻 등록/확인/변경 → 마지막 언급 → 다음 확인 예정) + **세대별 검색 관심 곡선**(`generation-curves.tsx`, 네이버 데이터랩 5세대, 단색 단계·점선·선 끝 라벨, 피크 점). 한국어 용어에만 곡선이 있음(`/terms/{id}/generations`).
- **나라 페이지** `/country/[code]`: 지금 뜨는 것(카테고리별), 왜 지금 뜨나, 이 나라에서 확인된 표현, 세대 분포 막대. 지구 패널의 '나라 페이지' 링크.
- **오늘의 변화** `/updates`: 새로 포착·뜻 확인·뜻 변경·급증 조사·재확인·검수 결정을 종류별로(`/updates` API = terms/meanings/explanations/research_log/review 결정의 최근 48시간). 지구 패널 머리에 "오늘의 변화 N건" 링크, 푸터에도.
- **메시지 해석 신뢰 표시**: 각 설명 아래 "근거 N · 마지막 확인 날짜 · 다음 확인 D일 후".
- **주제 나라별 차이**: 자리표시자 대신 `pipeline/topics.py` 가 근거로부터 서술(Gemma) — 확신 ≥0.5 만 표시, 현지 밈 이름은 근거에 실재하는 것만.

검증: 8개 경로 200, 스크린샷 `live-*`(지구 KR 패널·나라 페이지·용어 페이지 곡선·오늘의 변화). 배터리(`explain-check.mjs`)는 예시 모드 전용이라 api 모드 서버에서는 돌리지 않는다.

확인 후 손질(11:20): 시각은 한국어 화면 KST·영어 UTC(`fmtDateTime`), 타임라인 '다음 확인'은 가장 최근 사건 기준, 세대 곡선은 주 단위로 바꾸고 선 끝 라벨 겹침 방지. 알게 된 것: 헤드리스 크롬 캡처에서 텔루구·타이 글자가 깨져 보이는 건 폰트 문제(실제 브라우저는 정상). Gemma 분류가 '논술·띠별 운세'를 스포츠·이벤트에 넣는 등 카테고리 7개가 뉴스형 검색어를 다 담지 못한다 → 카테고리에 '뉴스·사회'를 추가할지 검토.


---

## 9차 (2026-09-15 11:40) · 사전을 위키처럼

사용자: "사전이 나무위키·위키백과처럼 나왔으면. 상세에 추세 나오는 건 좋다."

- **색인 페이지** `components/dictionary-list.tsx`: 큰 검색창 + "표현 N개 · 마지막 갱신", 왼쪽에 분류(건수)·언어·세대·나라·내 세대 토글·최근 바뀐 문서 8개, 오른쪽에 **첫 글자 색인**(한글 초성 ㄱ~ㅎ → A~Z → 0-9 → 그 밖의 문자; 영어 화면은 A~Z 먼저, `lib/dictionary/index.ts`). 항목 한 줄: 표제어·다른 표기·한 줄 뜻·분류·세대·확인 중 표시. 좁은 화면은 필터를 접어 둠.
- **문서 페이지** `app/dictionary/[termId]/page.tsx`: 목차(있는 절만 번호 매김) → 1 뜻 → 2 유래(각주 [1][2]) → 3 쓰임과 주의 → 4 나라별 차이(보드 주제의 변형; 지구로 가는 링크) → 5 추세(문장·스파크라인·세대×나라 표) → 6 세대별 관심 곡선(한국어 용어) → 7 포착에서 확인까지 → 8 관련 표현(다른 표기·같은 분류) → 9 출처(번호·발췌) → 10 변경 기록. 오른쪽 **정보상자**(고정): 분류·언어·상태·추세·세대·나라·처음/마지막 언급·다음 확인·근거 수·판 수.
- 디자인 등록부 유지(하얀 바탕, hairline, 색 없음). 정보상자 머리만 옅은 회색 띠.

### 9차 보충 (13:30) · 사전은 확인된 항목만

- 공개 사전(색인·문서·메시지 해석 매칭)은 API 기본값대로 `verified` 항목만 받는다. '확인 중' 항목은 관리자 검수 큐에서만 보인다. 색인 사이드바의 '확인 중 N' 은 그래서 0 이 정상이고, 값이 있으면 API 를 `?status=all` 로 부른 것이다.
- **재시작 주의**: Next 는 `fetch(..., { next: { revalidate } })` 응답을 `.next/cache/fetch-cache` 에 디스크로 남기고, 재검증 때 API 가 404 를 주면 옛 응답을 계속 낸다. 사전에서 항목을 제외(retired)한 뒤 화면에 남아 있으면 그 폴더를 지우고 재시작한다. `lib/data.ts` 의 `getTermRecord` 는 API 404 를 예시 데이터로 되살리지 않는다(서버가 죽었을 때만 예시로 내려감).
