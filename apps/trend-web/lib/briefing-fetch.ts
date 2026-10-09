/** 브리핑 요청 순서. 요약 문장을 처음 쓰는 요청은 모델을 기다리느라 늦을 수 있다 – 지역 하나만 고른 브리핑 첫 요청이
 *  웹의 기다림을 넘겨 화면 전체가 '불러오지 못함'이었다(10-09 운영). 그래서 요약 요청이 늦거나 실패하면 모델을 부르지 않는
 *  요청(summary=false)으로 한 번 더 받아 규칙 문장으로 연다. 끊긴 요청도 API 는 끝까지 돌아 요약을 캐시에 남기므로 다음 방문은 AI 요약이다. */
export const SUMMARY_WAIT_MS = 15_000;
export const LISTS_WAIT_MS = 15_000;

export async function loadBriefing(load: (summary: boolean, waitMs: number) => Promise<Response>): Promise<Response> {
  try {
    const res = await load(true, SUMMARY_WAIT_MS);
    if (res.ok) return res;
  } catch {
    // 시간 초과·연결 실패 – 아래에서 목록만 받는다
  }
  return load(false, LISTS_WAIT_MS);
}
