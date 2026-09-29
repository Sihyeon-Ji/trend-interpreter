"use client";

import { ErrorState } from "@/components/lab/o-report/state";

/* 트렌드 서버가 답하지 않을 때 — 예시 데이터로 바꿔 넣지 않고 다시 불러오기를 준다 */
export default function ReportError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return <ErrorState retry={retry} />;
}
