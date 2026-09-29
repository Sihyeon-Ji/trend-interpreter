import { cn } from "@/lib/utils";

/* 내용 칸. 데이터 화면은 최대 1200px, 읽는 화면(사전 항목·메시지 해석)은 760px — 왼쪽 정렬(메뉴 옆에 붙인다). */
export function PageShell({ children, width = "wide" }: { children: React.ReactNode; width?: "wide" | "narrow" }) {
  return (
    <main id="main" className="w-full flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <div className={cn(width === "wide" ? "max-w-[1200px]" : "max-w-[760px]")}>{children}</div>
    </main>
  );
}
