/* 자동 생성 — 수정 금지. 원본: src/trend_agents/schemas.py → scripts/export_schema.py → pnpm contract */

export type TermId = string;
export type Canonical = string;
export type Lang = string;
export type Aliases = string[];
export type Category = "slang" | "meme" | "song" | "drama" | "dance" | "news" | "geopolitics" | "product" | "other";
export type Status = "candidate" | "researching" | "needs_review" | "verified" | "retired";
export type Lifecycle = "emerging" | "rising" | "peak" | "steady" | "declining" | "dormant" | "unknown";
export type Diffusion = ("underground" | "spreading" | "mainstream" | "fading") | null;
export type RiskLevel = ("none" | "caution" | "avoid") | null;
export type RiskReasons = string[];
export type RiskCheckedAt = string | null;
export type RiskHuman = ("none" | "caution" | "avoid") | null;
export type RiskRuleLevel = ("none" | "caution" | "avoid") | null;
export type RiskDecidedBy = string | null;
export type RiskDecidedAt = string | null;
export type FirstSeen = string | null;
export type LastSeen = string | null;
/**
 * 뜻, 1~2문장
 */
export type Definition = string;
/**
 * 줄임말 풀이. 예: 자만추 → 자연스러운 만남 추구. 아니면 null
 */
export type Expansion = string | null;
/**
 * 유래. 어디서 언제. 모르면 'unknown'
 */
export type Origin = string;
/**
 * 뉘앙스·사용 맥락·주의점
 */
export type Nuance = string;
export type Generations = ("10s" | "20s" | "30s" | "40s" | "50s+" | "all")[];
/**
 * ISO 국가코드
 */
export type Regions = string[];
export type SelfConfidence = number;
/**
 * 유행어·밈·줄임말·챌린지·노래 후렴 같은 '표현'인가. 상품·기관·인물·정책·일반 단어면 false
 */
export type IsExpression = boolean;
export type MeaningId = string;
export type TermId1 = string;
export type Version = number;
export type Confidence = number;
export type Verification = "unverified" | "verified_auto" | "verified_human" | "rejected";
export type ValidFrom = string;
export type ValidTo = string | null;
export type CreatedBy = string;
/**
 * grounding 이 돌려준 출처 URL
 */
export type Citations = string[];
/**
 * 뜻, 1~2문장
 */
export type Definition1 = string;
/**
 * 줄임말 풀이. 예: 자만추 → 자연스러운 만남 추구. 아니면 null
 */
export type Expansion1 = string | null;
/**
 * 유래. 어디서 언제. 모르면 'unknown'
 */
export type Origin1 = string;
/**
 * 뉘앙스·사용 맥락·주의점
 */
export type Nuance1 = string;
export type Generations1 = ("10s" | "20s" | "30s" | "40s" | "50s+" | "all")[];
/**
 * ISO 국가코드
 */
export type Regions1 = string[];
export type SelfConfidence1 = number;
/**
 * 유행어·밈·줄임말·챌린지·노래 후렴 같은 '표현'인가. 상품·기관·인물·정책·일반 단어면 false
 */
export type IsExpression1 = boolean;
export type Definition2 = string;
/**
 * 줄임말 풀이. 원문 표기를 남기고 뜻만 옮긴다
 */
export type Expansion2 = string | null;
export type Origin2 = string;
export type Nuance2 = string;
/**
 * 쉽게 풀어 쓴 표현. 뜻이 따로 없는 감탄사면 null
 */
export type Plain = string | null;
export type EvidenceId = string;
export type Kind = "short" | "news" | "datalab" | "web" | "community" | "human" | "wiki";
export type Url = string;
export type Title = string;
export type SourceDomain = string;
export type ObservedAt = string;
/**
 * 근거가 되는 원문 문장
 */
export type Excerpt = string;
/**
 * 발췌가 우리 모델이 쓴 문장인가 (쇼츠 해석 등). 화면에는 보이되 검증 앵커로는 제목만 본다
 */
export type Derived = boolean;
export type SegmentId = string;
export type Generation = "10s" | "20s" | "30s" | "40s" | "50s+" | "all";
export type Region = string;
export type VideoId = string;
export type Url1 = string;
export type Title1 = string;
export type Channel = string;
export type PublishedAt = string;
export type DurationSec = number;
export type ViewCount = number;
export type LikeCount = number;
export type CommentCount = number;
export type Region1 = string;
export type CategoryId = string | null;
export type Tags = string[];
export type Source = string;
export type Url2 = string;
export type Language = string;
/**
 * 영상에서 실제로 일어나는 일, 2문장
 */
export type Summary = string;
/**
 * 유행어/밈/노래/드라마 이름. 원어 그대로
 */
export type Name = string;
export type Kind1 = "slang" | "meme" | "song" | "drama" | "dance" | "news" | "geopolitics" | "product" | "other";
/**
 * 유래 가설. 어디서 언제 시작됐는지. 모르면 'unknown'
 */
export type OriginHypothesis = string;
export type Confidence1 = number;
/**
 * 영상 속에서 이 표현이 실제로 나온 대사·자막 한 줄, 원어 그대로 120자 안. 말하거나 보이지 않았으면 빈 문자열
 */
export type Quote = string;
export type Memes = MemeRef[];
export type TargetGeneration = ("10s" | "20s" | "30s" | "40s" | "50s+" | "all")[];
export type WhyViral = string;
/**
 * 이 문화권/세대 밖의 사람에게 맥락 설명 (한국어)
 */
export type ExplainForOutsider = string;
/**
 * 브랜드/기관이 쓰면 위험한 이유 (조롱, 정치, 비하 유래, 유행 소멸 등)
 */
export type RiskFlags = string[];
export type DetectedGeneration = "10s" | "20s" | "30s" | "40s" | "50s+" | "all";
export type SlangTerms = string[];
export type PlainExplanation = string;
export type Confidence2 = number;
export type Title2 = string;
export type Link = string;
export type PublishedAt1 = string | null;
export type Source1 = string;
export type Region2 = string;
export type Query = string | null;
/**
 * 제품이 무엇인지 한 줄 (120자 안)
 */
export type Product = string;
/**
 * 제품 분야
 */
export type Category1 =
  | "food_drink"
  | "fashion_beauty"
  | "tech"
  | "game"
  | "entertainment"
  | "travel"
  | "finance"
  | "health_fitness"
  | "education"
  | "lifestyle";
/**
 * 이 제품 홍보가 전하고 싶은 느낌 1~3개
 */
export type Feelings = (
  | "joy"
  | "hype"
  | "cute"
  | "funny"
  | "relatable"
  | "comfort"
  | "pride"
  | "surprise"
  | "sarcasm"
  | "frustration"
  | "tired"
  | "romance"
  | "nostalgia"
  | "cool"
)[];
/**
 * 핵심 가치 1~3개 (예: 시원함, 한정판)
 */
export type Values = string[];
/**
 * 어떤 장면·상황에서 쓰이나
 */
export type Scene = string;
export type Colors = string[];
/**
 * 이 홍보에서 피해야 할 표현·주제
 */
export type Avoid = string[];
export type Platform = "instagram" | "x";
/**
 * 게시글 본문 (목표 지역 언어). 고른 밈을 그대로 넣는다
 */
export type Text = string;
/**
 * 해시태그 3~6개, # 없이, 띄어쓰기 없이
 */
export type Hashtags = string[];
/**
 * 이 안이 밈을 어떻게 썼는지 한 문장 (마케터가 읽는 설명, 화면 언어)
 */
export type NoteKo = string;
export type Copies = SocialCopy[];
export type Title3 = string;
export type DurationS = number;
export type StartS = number;
export type EndS = number;
/**
 * 화면에 보이는 것 (목표 지역 언어)
 */
export type Visual = string;
/**
 * 자막 (목표 지역 언어)
 */
export type Caption = string;
/**
 * 대사·내레이션 (목표 지역 언어)
 */
export type Line = string;
export type Scenes = ScriptScene[];
/**
 * 대본 설명 (마케터가 읽는 설명, 화면 언어)
 */
export type NoteKo1 = string;
/**
 * 썸네일 주요 문구 (목표 지역 언어)
 */
export type Headline = string;
/**
 * 배치 (마케터가 읽는 설명, 화면 언어)
 */
export type Layout = string;
/**
 * 색 (화면 언어)
 */
export type Colors1 = string[];
/**
 * 인물·제품 위치 (마케터가 읽는 설명, 화면 언어)
 */
export type Subject = string;
/**
 * 썸네일 설명 (화면 언어)
 */
export type NoteKo2 = string;

/**
 * 프론트가 소비하는 모델 묶음. $defs 에 전부 나온다.
 */
export interface Contract {
  term: Term;
  meaning: Meaning;
  meaning_draft: MeaningDraft;
  meaning_text: MeaningText;
  evidence: Evidence;
  segment: Segment;
  shorts_video: ShortsVideo;
  shorts_interpretation: ShortsInterpretation;
  generation_read: GenerationRead;
  news_item: NewsItem;
  product_brief: ProductBrief;
  content_draft: ContentDraft;
}
export interface Term {
  term_id: TermId;
  canonical: Canonical;
  lang?: Lang;
  aliases?: Aliases;
  category?: Category;
  status?: Status;
  lifecycle?: Lifecycle;
  diffusion?: Diffusion;
  risk_level?: RiskLevel;
  risk_reasons?: RiskReasons;
  risk_checked_at?: RiskCheckedAt;
  risk_human?: RiskHuman;
  risk_rule_level?: RiskRuleLevel;
  risk_decided_by?: RiskDecidedBy;
  risk_decided_at?: RiskDecidedAt;
  first_seen?: FirstSeen;
  last_seen?: LastSeen;
}
/**
 * 검증 게이트를 거쳐 저장된 버전. 뜻이 바뀌면 새 version 을 만들고 이전 것은 valid_to 를 닫는다(위키식 이력).
 */
export interface Meaning {
  definition: Definition;
  expansion?: Expansion;
  origin: Origin;
  nuance: Nuance;
  generations: Generations;
  regions: Regions;
  self_confidence: SelfConfidence;
  is_expression?: IsExpression;
  meaning_id: MeaningId;
  term_id: TermId1;
  version: Version;
  confidence: Confidence;
  verification?: Verification;
  valid_from: ValidFrom;
  valid_to?: ValidTo;
  created_by?: CreatedBy;
  citations?: Citations;
}
/**
 * 리서치 에이전트 출력. 검증 게이트를 통과하기 전까지는 Meaning 이 아니다.
 */
export interface MeaningDraft {
  definition: Definition1;
  expansion?: Expansion1;
  origin: Origin1;
  nuance: Nuance1;
  generations: Generations1;
  regions: Regions1;
  self_confidence: SelfConfidence1;
  is_expression?: IsExpression1;
}
/**
 * 한 언어로 된 뜻 묶음. 로컬 Gemma 가 언어별로 만들어 저장한다. 용어 원문(canonical)은 번역 대상이 아니다.
 */
export interface MeaningText {
  definition: Definition2;
  expansion?: Expansion2;
  origin: Origin2;
  nuance: Nuance2;
  plain?: Plain;
}
export interface Evidence {
  evidence_id: EvidenceId;
  kind: Kind;
  url: Url;
  title?: Title;
  source_domain: SourceDomain;
  observed_at: ObservedAt;
  excerpt?: Excerpt;
  derived?: Derived;
}
/**
 * 세대 × 국가. 확산 경로의 노드.
 */
export interface Segment {
  segment_id: SegmentId;
  generation: Generation;
  region: Region;
}
export interface ShortsVideo {
  video_id: VideoId;
  url: Url1;
  title: Title1;
  channel: Channel;
  published_at: PublishedAt;
  duration_sec: DurationSec;
  view_count?: ViewCount;
  like_count?: LikeCount;
  comment_count?: CommentCount;
  region: Region1;
  category_id?: CategoryId;
  tags?: Tags;
  source: Source;
}
/**
 * Gemini 가 쇼츠 하나를 직접 보고 내놓는 해석.
 */
export interface ShortsInterpretation {
  url: Url2;
  language: Language;
  summary: Summary;
  memes: Memes;
  target_generation: TargetGeneration;
  why_viral: WhyViral;
  explain_for_outsider: ExplainForOutsider;
  risk_flags?: RiskFlags;
}
export interface MemeRef {
  name: Name;
  kind: Kind1;
  origin_hypothesis: OriginHypothesis;
  confidence: Confidence1;
  quote?: Quote;
}
/**
 * 로컬 Gemma 가 텍스트 한 조각을 읽고 내놓는 세대 판정.
 */
export interface GenerationRead {
  detected_generation: DetectedGeneration;
  slang_terms: SlangTerms;
  plain_explanation: PlainExplanation;
  confidence: Confidence2;
}
export interface NewsItem {
  title: Title2;
  link: Link;
  published_at: PublishedAt1;
  source: Source1;
  region: Region2;
  query?: Query;
}
/**
 * 사진이나 홍보 문구를 읽은 제품 설명. 요청 때 한 번 만든다(Gemini, 개발 환경은 로컬 Gemma 또는 고정 예시).
 * 추천 점수에는 category·feelings 만 쓰고(닫힌 낱말), 나머지는 이유 서술과 화면 표시에 쓴다.
 */
export interface ProductBrief {
  product: Product;
  category: Category1;
  feelings: Feelings;
  values?: Values;
  scene?: Scene;
  colors?: Colors;
  avoid?: Avoid;
}
/**
 * 생성 한 번의 결과: 인스타그램 2안·X 2안, 숏폼 대본 하나, 썸네일 구성안 하나.
 */
export interface ContentDraft {
  copies: Copies;
  script: ShortScript;
  thumbnail: ThumbnailPlan;
}
/**
 * SNS 카피 한 안. 글은 목표 지역의 언어, note_ko 는 마케터가 읽는 설명(화면 언어 — 이름은 예전 그대로).
 */
export interface SocialCopy {
  platform: Platform;
  text: Text;
  hashtags?: Hashtags;
  note_ko?: NoteKo;
}
/**
 * 틱톡·릴스용 15~30초 대본.
 */
export interface ShortScript {
  title: Title3;
  duration_s: DurationS;
  scenes: Scenes;
  note_ko?: NoteKo1;
}
export interface ScriptScene {
  start_s: StartS;
  end_s: EndS;
  visual: Visual;
  caption?: Caption;
  line?: Line;
}
export interface ThumbnailPlan {
  headline: Headline;
  layout: Layout;
  colors?: Colors1;
  subject?: Subject;
  note_ko?: NoteKo2;
}
