import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone", // Cloud Run 컨테이너용 (apps/trend-web/Dockerfile)
  // 개발 서버만의 설정. e2e 컨테이너는 'web' 이라는 이름으로 접속하는데, Next 는 다른 출처의 개발 자원 요청을 막아
  // 화면이 하이드레이션되지 않았다 — 링크만 누르는 테스트는 통과하고, 입력 폼을 쓰는 테스트는 멈췄다(2026-09-29).
  allowedDevOrigins: ["web", "127.0.0.1"],
};

export default nextConfig;
