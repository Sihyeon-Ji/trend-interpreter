/** 다른 사이트에서 보낸 쓰기는 받지 않는다. 운영 프록시는 Next.js 에 내부 주소를 넘기면서 공개 Host 를 지키므로 그것을 본다.
 *  Origin 이 없거나 모양이 틀리면 거부한다(fail closed). 승인 배치 결정과 문구 승인 기록이 같이 쓴다. */
export function isSameOrigin(req: Request): boolean {
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? new URL(req.url).host;
  try {
    const origin = new URL(req.headers.get("origin") ?? "");
    return ["https:", "http:"].includes(origin.protocol) && origin.host === host;
  } catch {
    return false;
  }
}
