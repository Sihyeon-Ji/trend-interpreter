/* 읽는 사람 설정. 로그인한 사람의 계정에 저장된다(2026-09-16). 익명 방문자는 설정을 갖지 않고, 설명은 중립으로 나간다.
   받는 것: 닉네임·세대·나라·(10대면) 만 14세 이상 확인. 성별·생년월일은 받지 않는다. */
import type { Generation } from "./types";

export const READER_GENS: Exclude<Generation, "all">[] = ["10s", "20s", "30s", "40s", "50s+"];
/** 목표 지역(ADR 0001) — 백엔드 config.REGIONS_FOCUS 와 같다. 중국 본토는 없다. */
export const TARGET_REGIONS = ["KR", "JP", "TW", "HK", "TH", "VN", "ID", "PH", "MY", "SG"];
/** 카피·검사·포스터를 만들 수 있는 시장 — 목표 지역 + 영어권(GLOBAL). 백엔드 config.WRITE_REGIONS 와 같다 (Plan 20) */
export const WRITE_REGIONS = [...TARGET_REGIONS, "GLOBAL"];
/** 만들기(Plan 20)의 시장 — 한국·일본·영어권. 서버 화면과 클라이언트 컴포넌트가 함께 쓰므로 여기에 둔다 */
export const MAKE_MARKETS = ["KR", "JP", "GLOBAL"] as const;
export const READER_REGIONS = ["KR", "JP", "TW", "HK", "TH", "VN", "ID", "PH", "MY", "SG", "IN", "AU", "US", "CA", "GB", "DE", "FR", "ES", "IT", "BR", "MX", "AR", "TR", "SA", "EG", "NG", "ZA"];

export interface Reader {
  nick?: string;
  gen?: Exclude<Generation, "all">;
  region?: string;
  adult?: boolean; // 10대일 때 만 14세 이상 확인
}

export function parseReader(raw: string | undefined): Reader {
  if (!raw) return {};
  try {
    const o = JSON.parse(raw) as Reader;
    return {
      nick: typeof o.nick === "string" ? o.nick.slice(0, 20) : undefined,
      gen: READER_GENS.includes(o.gen as never) ? o.gen : undefined,
      region: READER_REGIONS.includes(o.region ?? "") ? o.region : undefined,
      adult: !!o.adult,
    };
  } catch {
    return {};
  }
}

export const hasReader = (r: Reader) => !!(r.nick || r.gen || r.region);

/** 로그인 뒤 돌아갈 주소. 같은 사이트의 경로만 받는다(열린 리다이렉트 방지) — '/' 로 시작하고 '//'·'/\' 가 아니며,
 *  로그인 화면이나 API 로 되돌아가지 않는다. 받을 수 없으면 null — 부르는 쪽이 계정에 맞는 기본값을 고른다. */
export function safeNext(next: string | null | undefined): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return null;
  if ([...next].some((c) => c.charCodeAt(0) < 32)) return null;   // 줄바꿈·제어 문자를 끼운 주소
  if (/^\/(login|api)(\/|\?|#|$)/.test(next)) return null;
  return next;
}

/** 로그인한 뒤 갈 곳: 요청한 주소가 있으면 그곳, 없으면 검수자는 관리 화면, 그 밖의 계정은 첫 화면. */
export const afterLogin = (next: string | null, reviewer: boolean) => next ?? (reviewer ? "/admin" : "/");
