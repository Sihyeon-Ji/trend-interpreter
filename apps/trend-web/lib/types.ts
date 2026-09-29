/* 계약 타입은 lib/contract/types.ts (자동 생성) 에서 온다. 여기는 프론트 전용 뷰 모델만. */
import type { Diffusion, Evidence, Lifecycle, Meaning, MeaningText, MemeRef, RiskLevel, Segment, Term } from "./contract/types";
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
  note?: string;
}

export interface ReviewItem {
  term_id: string;
  canonical: string;
  proposed: Meaning;
  reasons: string[];
  evidence_count: number;
  queued_at: string;
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
  communities: SourceCount[];
  tone: Tone;
  evidences: EvidenceBrief[];
  last_seen?: string | null;
  last_used?: string | null;      // 고른 지역에서 가장 최근에 쓰인 글의 때
}

export interface KeywordBoard {
  generated_at: string;
  regions: string[];
  counts: Record<string, number>;
  rising: KeywordCard[];
  fading: KeywordCard[];
  caution: KeywordCard[];
}
