import { PROTOTYPE_HTML } from "@/lib/lab/t-studio";

/* 초안 5의 한 파일짜리 화면을 그대로 내보낸다. 예시 데이터만 들어 있고 백엔드를 부르지 않는다. */
export const dynamic = "force-static";

export function GET() {
  return new Response(PROTOTYPE_HTML, { headers: { "content-type": "text/html; charset=utf-8" } });
}
