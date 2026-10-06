import { cn } from "@/lib/utils";

/* 내용 칸 (Plan 20 A안): 위 막대와 같은 1280px 틀 안에서 왼쪽 정렬. 읽는 화면(사전 항목·메시지 해석)은 본문을 760px 로 묶는다. */
export function PageShell({ children, width = "wide" }: { children: React.ReactNode; width?: "wide" | "narrow" }) {
  return (
    <main id="main" className="mx-auto w-full max-w-[1280px] flex-1 px-4 py-6 sm:px-6 lg:py-10 xl:px-8">
      <div className={cn(width === "narrow" && "max-w-[760px]")}>{children}</div>
    </main>
  );
}
