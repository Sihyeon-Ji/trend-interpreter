import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone", // Cloud Run 컨테이너용 (apps/trend-web/Dockerfile)
  // 개발 서버만의 설정. e2e 컨테이너는 'web' 이라는 이름으로 접속하는데, Next 는 다른 출처의 개발 자원 요청을 막아
  // 화면이 하이드레이션되지 않았다 — 링크만 누르는 테스트는 통과하고, 입력 폼을 쓰는 테스트는 멈췄다(2026-09-29).
  // 같은 망의 다른 PC 에서 개발 서버를 열 때는 DEV_ORIGINS=192.168.x.x 처럼 넘긴다(주소를 저장소에 박지 않는다, 10-06)
  allowedDevOrigins: ["web", "127.0.0.1", ...(process.env.DEV_ORIGINS?.split(",").map((s) => s.trim()).filter(Boolean) ?? [])],
};

export default nextConfig;
