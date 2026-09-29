/* 계약 타입은 lib/contract/types.ts (자동 생성) 에서 온다. 여기는 프론트 전용 뷰 모델만. */
import type { Diffusion, Evidence, Lifecycle, Meaning, MeaningDraft, MeaningText, MemeRef, ProductBrief, RiskLevel, Segment, ShortScript, SocialCopy, Term, ThumbnailPlan } from "./contract/types";
import type { EvidenceBrief } from "./trends/types";

export type {
  Term,
  Meaning,
  MeaningDraft,
  MeaningText,
  Evidence,
  Segment,
  MemeRef,
  ShortsInterpretation,
  Generation,
  Lifecycle,
  Verification,
  ProductBrief,
  SocialCopy,
  ShortScript,
  ScriptScene,
  ThumbnailPlan,
} from "./contract/types";

export type TermStatus = NonNullable<Term["status"]>;
export type Category = MemeRef["kind"];
export type EvidenceKind = Evidence["kind"];

/** Term ─USED_BY(first_seen, share)→ Segment */
export interface TermUsage {
  segment: Segment;
  first_seen: string;
  share: number;
}

/** 주간 언급 수 (쇼츠 등장 + 뉴스 + 데이터랩 합산). 생애주기 판정의 입력. */
export interface WeeklyPoint {
  week_start: string;
  count: number;
}

/** 화면이 소비하는 사전 항목 한 건. 백엔드 API 응답 형태로 그대로 쓸 예정. */
export interface TermRecord {
  term: Term;
  category: Category; // TODO(contract): Term 에 category 필드 추가 검토 (schemas.py + DDL)
  plain: string; // 쉬운 표현 (한국어). 빈 문자열이면 뜻이 따로 없는 감탄사
  en?: MeaningText; // 현행 뜻의 영어판. 백엔드 로컬 Gemma 가 만들어 저장 (Meaning.translations 예정)
  meanings: Meaning[]; // version 오름차순
  evidences: Evidence[];
  usage: TermUsage[];
  weekly: WeeklyPoint[];
  ko?: MeaningText | null;  // 한국어 화면이 쓸 뜻 (일본어·영어 표제어의 뜻을 한국어로)
  recheck_days: number;
  media?: TermMedia[];     // 대표 그림·영상 (주소만 보관, 라이선스 함께)
  gate_reasons?: string[]; // needs_review 인 경우 게이트가 남긴 사유
}

/** 대표 그림·영상. 그림은 위키미디어 공용의 자유 라이선스만, 영상은 유튜브 공식 플레이어로 끼운다. */
export interface TermMedia {
  kind: "image" | "video";
  url: string;
  page_url: string;
  title: string;
  license: string;
  attribution: string;
}

export interface PipelineStage {
  key: string;
  label: string;
  count_24h: number;
  status: "ok" | "warn" | "zero";
  note?: string | null;
  // 관리 화면 '수집 현황' — 마지막 실행의 상태(없으면 24시간 안에 실행 없음)와 그 단계의 마지막 실행 시각
  run_status?: "ok" | "idle" | "skipped" | "error" | null;
  last_started_at?: string | null;
  last_finished_at?: string | null;
}

/** 검수 제안의 종류 (Plan 12, views.ReviewKind) — 새 말(조사 결과) · 고칠 안 · 위키끼리 다름 · 사전에서 뺄지 */
export type ReviewKind = "new" | "correction" | "conflict" | "retire";

/** 제안의 근거가 된 참고 문서 한 쪽 (views.ReviewDoc). 위키끼리 다를 때는 고르는 설명이다 — proposal 이 있는 것만 고를 수 있다. */
export interface ReviewDoc {
  wiki: string;
  url: string;
  summary: string;
  proposal?: MeaningDraft | null;
}

/** 검수 한 건 (views.ReviewItem). new: proposed 가 확인 전인 지금 판, current 는 그 앞의 확인된 판(없으면 새 말).
 *  correction·conflict·retire: current 가 공개 중인 지금 뜻 — 제안이 올라와 있어도 사전에 그대로 실려 있다. */
export interface ReviewItem {
  term_id: string;
  canonical: string;
  kind: ReviewKind;
  meaning_id?: string | null;     // 결정과 함께 되돌려 보낼 뜻 — new 는 proposed, 나머지는 current. 그사이 바뀌었으면 서버가 409
  token?: string;                 // 이 제안의 표(올린 때·내용). 결정과 함께 보내고, 그사이 다른 제안이 올라왔으면 서버가 409
  proposed?: Meaning | null;      // new: 검수할 뜻
  draft?: MeaningDraft | null;    // correction: 고칠 안 (승인하면 새 판)
  reasons: string[];
  evidence_count: number;
  queued_at: string;
  // 근거를 보고 결정하도록: 표제어 말, 지금 사전에 실린 뜻(없으면 새 뜻), 표제어가 든 근거 상위 5건, 최근 12주 언급
  lang?: string | null;
  current?: Meaning | null;
  evidences?: Evidence[];
  weekly?: WeeklyPoint[];
  docs?: ReviewDoc[];             // correction·retire: 참고 문서 · conflict: 문서마다의 설명
}

/* 키워드 대시보드 (Plan 04) — 백엔드 pipeline/views.py 의 KeywordCard·KeywordBoard 와 1:1. 값은 pipeline/dashboard.py 규칙이 채운다. */
export interface SearchHit { region: string; query: string; source: string; date: string; rank?: number | null; traffic?: string | null }
export interface SourceCount { domain: string; count: number }
export interface GenPeak { generation: string; date: string }
export interface Tone { positive: number; neutral: number; negative: number }

export interface KeywordCard {
  term_id: string;
  canonical: string;
  lang: string;
  category: string;
  gloss_ko: string;
  gloss_en: string;
  regions: string[];              // 목표 지역 코드, 목표 지역 밖에서 널리 쓰이면 GLOBAL
  lifecycle: Lifecycle;
  diffusion?: Diffusion;
  risk_level?: RiskLevel;
  risk_reasons: string[];
  risk_checked_at?: string | null; // 리스크 규칙을 돌린 때. 없으면 검사 전 — '근거 부족' 표시를 하지 않는다
  weekly: WeeklyPoint[];          // 최근 12주
  mentions_4w: number;
  search: SearchHit[];            // 고른 지역의 인기 검색어 기록
  gen_peaks: GenPeak[];           // 연령대별 검색 정점 (네이버 데이터랩, 한국어 표제어만)
  communities: SourceCount[];     // 늘 빈 목록 — 커뮤니티 사이트 이름은 이용자에게 내지 않는다(ADR 0003). 화면은 읽지 않는다
  tone: Tone;
  evidences: EvidenceBrief[];     // 최근 근거 (커뮤니티·SNS 글은 빼고)
  last_seen?: string | null;
  last_used?: string | null;      // 고른 지역에서 가장 최근에 쓰인 글의 때
}

export type KeywordList = "rising" | "fading" | "caution";

/** 세계 지도의 지역 한 곳 — 쪽과 상관없이 그 지역 전체에서 센다 (views.RegionSummary) */
export interface RegionSummary {
  caution: number;                                              // 주의가 필요한 밈 수
  top: { term_id: string; canonical: string; lang: string } | null;   // 지금 쓰이는 밈 1위, 없으면 식어 가는 밈 1위
}

export interface KeywordBoard {
  generated_at: string;
  regions: string[];
  counts: Record<string, number>;       // 지역마다 카드 수, 'ALL' 은 목표 지역 어디든(전 세계만인 것은 빼고)
  totals: Record<KeywordList, number>;  // 목록마다 전체 건수. 주의 밈은 쓰이는·식는 목록에도 있다(Plan 04)
  page: number;                         // 아래 세 목록에 실린 쪽 (1부터)
  page_size: number;
  rising: KeywordCard[];                // 그 쪽만
  fading: KeywordCard[];
  caution: KeywordCard[];
  summary?: Record<string, RegionSummary>;   // summary=1 로 물을 때만 — 지역마다(세계 지도)
}

/* 밈 추천 (Plan 07) — 백엔드 pipeline/views.py 의 RecommendItem·RecommendResult 와 1:1. 순위는 pipeline/recommend.py 규칙이 매긴다. */
export type FitCategory = ProductBrief["category"];
export type Feeling = ProductBrief["feelings"][number];
export type CampaignTone = "friendly" | "witty" | "premium";

export interface RecommendItem {
  term_id: string;
  canonical: string;
  lang: string;                   // 표제어의 말(KeywordCard.lang) — 원문에 lang 을 붙인다
  gloss_ko: string;
  gloss_en: string;
  regions: string[];
  diffusion?: Diffusion;
  lifecycle: Lifecycle;
  risk_level?: RiskLevel;
  risk_reasons: string[];
  risk_checked_at?: string | null; // 리스크 규칙을 돌린 때 — '근거 부족' 표시 여부
  matched_category: boolean;      // 제품 분야가 이 밈이 어울리는 분야에 있다
  any_category: boolean;          // 분야를 가리지 않는 반응·감탄 표현
  matched_feelings: Feeling[];
  // 고른 나라에서의 쓰임 — 파이프라인이 근거로 미리 써 둔 국가별 해석(확신 0.5 이상). 이유는 화면이 사전 뜻·겹친 낱말·이것으로 구성한다
  local_region?: string | null;
  local_note?: { ko: string; en: string } | null;
  write_regions: string[];        // 고른 지역 가운데 이 밈으로 결과물을 쓸 수 있는 곳 — '결과물 지역' 선택지
  score: number;
  evidences: EvidenceBrief[];
  pinned: boolean;                // 사전 항목의 '이 밈으로 만들기' 로 먼저 고른 밈 — 순위 밖이어도 목록 끝에 들어온다
}

export interface RecommendResult {
  brief?: ProductBrief | null;    // 고른 지역에 비교할 후보가 없으면 읽지 않는다
  brief_source: "gemini" | "local" | "sample" | "none";
  regions: string[];
  tone: CampaignTone;
  items: RecommendItem[];
  considered: number;
  untagged: number;
}

/* 콘텐츠 생성 (Plan 08) — 백엔드 pipeline/views.py 의 GenerationResult·Dropped 와 1:1. 결과는 저장하지 않는다. */
export type DropCode = "unsafe" | "no_meme" | "x_too_long" | "avoid_word";
export interface Dropped { id: string; code: DropCode; reason: string }   // reason 은 같은 문제의 한국어 설명(운영 기록용) — 화면은 code 로 쓴다

export interface GenerationResult {
  region: string;
  language: string;               // 결과물의 말 (목표 지역)
  tone: CampaignTone;
  memes: string[];
  copies: SocialCopy[];           // 사전 대조 검사를 통과한 안만
  script?: ShortScript | null;
  thumbnail?: ThumbnailPlan | null;
  dropped: Dropped[];             // 두 번 다 규칙 검사에 걸려 뺀 안과 이유
  model_calls: number;            // 생성 1, 다시 만들면 2
  source: "gemini" | "local" | "sample";
}

