import { RISK, STAGE, STAGE_ORDER, type Risk, type Stage } from "@/lib/lab/n-redesign/data";

/** 누가 정했나 — 규칙(실선)·모델(점선)·검수자(서명 잉크). 이 시안의 한 가지 장치. */
export function Who({ kind, children }: { kind: "rule" | "model" | "human" | "wait"; children?: React.ReactNode }) {
  const fallback = { rule: "규칙", model: "모델", human: "검수자", wait: "승인 대기" }[kind];
  return <span className="n-who" data-who={kind}>{children ?? fallback}</span>;
}

export function StageMark({ stage }: { stage: Stage }) {
  const at = STAGE_ORDER.indexOf(stage);
  return (
    <span className="n-stage">
      <i aria-hidden="true">{STAGE_ORDER.map((s, n) => <b key={s} data-on={n === at} />)}</i>
      <span>{STAGE[stage]}</span>
    </span>
  );
}

export function RiskText({ risk }: { risk: Risk }) {
  return <span className="n-risk" data-r={risk}>{RISK[risk]}</span>;
}

/** 12주 언급 추이 — 한 줄, 마지막 주에만 점. 값은 옆 칸(4주 언급)과 aria-label 로도 읽힌다. */
export function Spark({ values, w = 84, h = 22 }: { values: number[]; w?: number; h?: number }) {
  const max = Math.max(...values, 1);
  const pad = 3;
  const x = (i: number) => pad + (i * (w - pad * 2)) / (values.length - 1);
  const y = (v: number) => h - pad - (v / max) * (h - pad * 2);
  const d = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = values.length - 1;
  return (
    <svg className="n-spark" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img"
      aria-label={`12주 언급 추이, 첫 주 ${values[0]}회에서 마지막 주 ${values[last]}회`}>
      <title>{`첫 주 ${values[0]}회, 마지막 주 ${values[last]}회`}</title>
      <line x1={pad} x2={w - pad} y1={h - pad} y2={h - pad} stroke="#e5e5e5" strokeWidth="1" />
      <path d={d} fill="none" stroke="#000" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(last)} cy={y(values[last])} r="2.5" fill="#000" />
    </svg>
  );
}

/** 원문 낱말에 lang 을 붙인다. 번역하지 않는다. */
export function Orig({ lang, children, className }: { lang: string; children: React.ReactNode; className?: string }) {
  return <span lang={lang} className={className}>{children}</span>;
}
