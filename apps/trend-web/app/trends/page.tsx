import { redirect } from "next/navigation";

/** 대시보드가 첫 화면(/)이 됐다(디자인 개편 09-29). 예전 /trends 링크는 주소의 지역·목록을 그대로 들고 넘어간다. */
export default async function TrendsRedirect({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) for (const x of [v].flat()) if (x) q.append(k, x);
  redirect(q.size ? `/?${q}` : "/");
}
