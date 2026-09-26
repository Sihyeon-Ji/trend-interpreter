/* '지금 뜨는 것' — 나라 × 카테고리 보드와, 나라를 건너간 트렌드(주제)의 나라별 차이.
   사전(TermRecord)과는 별개의 뷰 모델. 원천(Google Trends·YouTube·뉴스)에는 카테고리가 없어 백엔드 분류 단계가 붙인다.
   계약(schemas.py) 반영 전이라 여기서만 정의한다. */

export type TrendCategory = "slang_meme" | "song_challenge" | "fashion_beauty" | "food" | "product" | "people_content" | "sports_event";
export const TREND_CATEGORIES: TrendCategory[] = ["slang_meme", "song_challenge", "fashion_beauty", "food", "product", "people_content", "sports_event"];

export type Change = "new" | "up" | "flat" | "down";
export type Text2 = { ko: string; en: string };

export interface TrendItem {
  id: string;
  region: string; // ISO 3166-1 alpha-2
  category: TrendCategory;
  term: string; // 원문 그대로 (번역하지 않는다)
  rank: number; // 그 나라·카테고리 안에서의 순위
  change: Change;
  gain_pct?: number;
  weekly: number[]; // 최근 12주 상대 언급량
  term_id?: string; // 사전에 있으면 연결
  topic_id?: string; // 나라를 건너간 트렌드면 연결
  note: Text2; // 무엇인지 한 줄. 뜻 풀이는 사전이 맡는다
}

/* 한 주제가 어느 나라에서 어떻게 달라졌나 */
export interface TopicVariant {
  region: string;
  local_name: string; // 그 나라에서 부르는 이름 (원문)
  since: string; // 처음 눈에 띈 때. dated 가 아니면 참고용이고 순서를 정하는 데 쓰지 않는다
  dated?: boolean; // since 에 날짜를 대는 출처가 있나 — 있어야 이동 경로의 한 점이 된다
  since_source?: Text2; // 그 출처 (예: 위키백과 일본어판 · 문서 생성)
  heat: number; // 지금 관심도 0~100 (주제 안에서 상대값)
  what_changed: Text2; // 나라별 차이 한 줄
  local_memes: { label: string; note: Text2 }[]; // 그 나라에서 생긴 밈·대사·놀이
  linked: { label: string; note: Text2; term_id?: string }[]; // 엮인 그 나라의 다른 트렌드
  term_id?: string;
}

export interface Topic {
  id: string;
  category: TrendCategory;
  name: Text2;
  summary: Text2; // 주제가 무엇인지 두 문장
  variants: TopicVariant[]; // 처음 나온 곳은 lib/trends/path.ts 의 originOf() 로만 — 날짜 근거가 둘 이상일 때만 정해진다
}

export type Trigger = "influencer" | "release" | "event" | "controversy" | "meme" | "promotion" | "holiday" | "sports" | "unknown";

export interface EvidenceBrief { kind: string; source_domain: string; title: string; url: string; observed_at: string }

/* 왜 지금 뜨나 — 급증 원인 설명 + 근거 요약 */
export interface TrendWhy {
  term: string;
  region: string;
  date: string;
  why_now: Text2;
  trigger: Trigger;
  actors: { name: string; role: string }[];
  first_signal: string | null;
  confidence: number;
  evidence_counts: Record<string, number>;
  evidence: EvidenceBrief[];
  updated_at: string;
}

export interface UpdateItem { kind: string; at: string; label: string; region?: string | null; term_id?: string | null; detail?: string | null }
export interface GenerationCurve { generation: string; points: [string, number][]; peak_date: string | null }
export interface Meta { last_run: string | null; board_generated_at: string | null; terms: number; explanations: number }

export interface TrendBoard {
  generated_at: string;
  items: TrendItem[];
  topics: Topic[];
  why: TrendWhy[];
}
