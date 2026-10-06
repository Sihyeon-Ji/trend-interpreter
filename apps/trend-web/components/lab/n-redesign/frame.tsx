"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Who } from "./bits";

const BASE = "/lab/n-redesign";
const NAV = [
  { href: BASE, label: "만들기", match: (p: string) => p === BASE },
  { href: `${BASE}/drafts`, label: "초안", match: (p: string) => p.startsWith(`${BASE}/drafts`) },
  { href: `${BASE}/explore`, label: "둘러보기", match: (p: string) => p.startsWith(`${BASE}/explore`) || p.startsWith(`${BASE}/term`) },
];

export function Frame({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  return (
    <>
      <a href="#n-main" className="n-skip">본문으로 건너뛰기</a>
      <header className="n-top">
        <div className="n-wrap">
          <Link href={BASE} className="n-brand"><b>Trend Interpreter</b><span>트렌드 통역</span></Link>
          <nav className="n-nav" aria-label="주 메뉴">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} aria-current={n.match(path) ? "page" : undefined}>{n.label}</Link>
            ))}
            <Link href="/explain">메시지 해석</Link>
            <Link href="/admin">검수 대기 <span className="n-count n-num" aria-label="3건">3</span></Link>
          </nav>
          <span className="n-me">김태우, 검수자</span>
        </div>
      </header>
      <main id="n-main" className="n-main">{children}</main>
      <footer className="n-foot">
        <div className="n-wrap">
          <div className="n-legend" aria-label="표지 읽는 법">
            <span><Who kind="rule" />규칙 코드가 정함</span>
            <span><Who kind="model" />모델이 씀</span>
            <span><Who kind="human" />사람이 승인</span>
          </div>
          <span className="n-note">시안 n-redesign. 예시 데이터로 그렸습니다.</span>
        </div>
      </footer>
    </>
  );
}
