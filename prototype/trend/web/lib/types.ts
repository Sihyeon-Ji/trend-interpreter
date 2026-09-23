/* 계약 타입은 lib/contract/types.ts (자동 생성) 에서 온다. 여기는 프론트 전용 뷰 모델만. */
import type { Evidence, Meaning, MeaningText, MemeRef, Segment, Term } from "./contract/types";

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
