import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone", // Cloud Run 컨테이너용 (web/Dockerfile)
};

export default nextConfig;
