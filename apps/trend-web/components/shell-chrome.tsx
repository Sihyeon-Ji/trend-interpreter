"use client";

import { usePathname } from "next/navigation";

/** 앱 틀의 겉(메뉴·예시 안내 줄·바닥글)을 두를지 정한다. 디자인 시안(/lab/*)은 자기 틀을 스스로 그리므로 내용만 둔다. */
export function ShellChrome({ skip, sidebar, banner, footer, children }: {
  skip: React.ReactNode; sidebar: React.ReactNode; banner: React.ReactNode; footer: React.ReactNode; children: React.ReactNode;
}) {
  if (usePathname().startsWith("/lab")) return <>{children}</>;
  return (
    <div className="ledger flex min-h-dvh flex-col">
      {skip}
      {sidebar}
      {banner}
      {children}
      {footer}
    </div>
  );
}
