import type { CSSProperties, ReactNode } from "react";
import { fitName, type TapeTone } from "@/lib/lab/o-editorial";

/** 라벨 테이프 — 단계·쓸 때 조심·새로 실림. 글자가 곧 상태라 색만으로 말하지 않는다. */
export function Tape({ tone, children }: { tone: TapeTone; children: ReactNode }) {
  return <span className="oe-tape" data-tone={tone}>{children}</span>;
}

/** 이름을 칸 폭에 맞춰 세운다. 줄은 여기서 나누고(낱말 사이, 띄어쓰기 없는 긴 일본어는 글자 수로), 크기는 CSS 가
 *  min(상한, 칸 폭 ÷ 가장 긴 줄의 폭) 으로 정한다. 줄 사이 띄어쓰기는 글 속에 남겨 화면 읽기·복사에서 이름이 붙지 않게. */
export function FitName({ name, lang, className = "", maxLines = 3, splitAbove }: {
  name: string; lang?: string; className?: string; maxLines?: number; splitAbove?: number;
}) {
  const { lines, em } = fitName(name, maxLines, splitAbove);
  const spaced = /\s/.test(name.trim());
  return (
    <span className={`oe-fit-name ${className}`} lang={lang} style={{ "--oe-em": em.toFixed(3) } as CSSProperties}>
      {lines.map((ln, i) => (
        <span key={i} className="oe-line" style={{ "--i": i } as CSSProperties}>
          {ln}
          {spaced && i < lines.length - 1 ? " " : null}
        </span>
      ))}
    </span>
  );
}
