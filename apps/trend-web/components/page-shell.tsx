/* 일반 페이지의 960px 컨테이너. 지도(/map)처럼 전폭이 필요한 페이지는 쓰지 않는다. */
export function PageShell({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto w-full max-w-[960px] flex-1 px-4 py-8 sm:px-6">{children}</main>;
}
