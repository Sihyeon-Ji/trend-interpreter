import { cp, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";

const envFile = new URL("../.env.local", import.meta.url);
if (existsSync(envFile)) process.loadEnvFile(envFile);

await mkdir(new URL("../.next/standalone/.next/", import.meta.url), {
  recursive: true,
});
await cp(
  new URL("../.next/static/", import.meta.url),
  new URL("../.next/standalone/.next/static/", import.meta.url),
  { recursive: true },
);
await cp(
  new URL("../public/", import.meta.url),
  new URL("../.next/standalone/public/", import.meta.url),
  { recursive: true },
);
process.env.HOSTNAME = process.env.ATLAS_HOSTNAME || "0.0.0.0";
process.env.PORT ||= "3000";
await import("../.next/standalone/server.js");
