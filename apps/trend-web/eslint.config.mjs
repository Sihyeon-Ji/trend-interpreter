import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // 디자인 초안 5(t-studio)의 원본 — 빌드 스크립트가 하나로 합치는 브라우저 전역 스크립트라 앱 규칙을 쓰지 않는다
    "lib/lab/t-studio/source/**",
  ]),
]);

export default eslintConfig;
