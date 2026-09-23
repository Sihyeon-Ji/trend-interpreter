import { redirect } from "next/navigation";

/** 지도가 첫 화면이 됐다(2026-09-16 결정). 예전 /map 링크는 그대로 열리게 둔다. */
export default async function MapRedirect({ searchParams }: { searchParams: Promise<{ region?: string; topic?: string }> }) {
  const sp = await searchParams;
  const q = new URLSearchParams(Object.entries(sp).filter(([, v]) => v) as [string, string][]).toString();
  redirect(q ? `/?${q}` : "/");
}
