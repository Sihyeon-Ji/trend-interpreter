/* 읽는 사람 설정. 로그인한 사람의 계정에 저장된다(2026-09-16). 익명 방문자는 설정을 갖지 않고, 설명은 중립으로 나간다.
   받는 것: 닉네임·세대·나라·(10대면) 만 14세 이상 확인. 성별·생년월일은 받지 않는다. */
import type { Generation } from "./types";

export const READER_GENS: Exclude<Generation, "all">[] = ["10s", "20s", "30s", "40s", "50s+"];
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
