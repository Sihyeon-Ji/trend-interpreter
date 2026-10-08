import type { Metadata } from "next";
import Link from "next/link";

/* 디자인 초안 검토 목록(/lab) — 지금 화면과 초안 넷을 같은 데이터로 오가며 본다. 운영 웹(:3100)이 아니라 초안 전용 빌드(:3200)에만 있다. */
export const metadata: Metadata = { title: "디자인 초안 · 트렌드 통역" };

type Draft = { href: string; name: string; direction: string; model: string; note: string; samples?: boolean };
const DRAFTS: Draft[] = [
  { href: "/lab/r-flow", name: "리디자인 A", direction: "작업 공간형", model: "Opus 5.5", note: "시장 × 다섯 단계 표가 요청이 끝날 때마다 칸칸이 차오른다. 밈은 옆 패널로 열리고 Ctrl K 로 찾는다(10-06)." },
  { href: "/lab/r-stage", name: "리디자인 B", direction: "무대형", model: "Opus 5.5", note: "세 시장이 지금 쓰이는 말을 들고 선 무대에서 초안이 차례로 조립된다. 일하는 시장이 앞으로 나온다(10-06)." },
  { href: "/lab/o-report", name: "초안 1", direction: "트렌드 리포트형", model: "Opus 5.5", note: "순위 목록과 추이 그래프 중심. 고른 밈을 오른쪽에서 미리 본다." },
  { href: "/lab/o-editorial", name: "초안 2", direction: "에디토리얼형", model: "Opus 5.5", note: "이번 주 호(號)처럼 읽는 밈 잡지. 큰 표제어와 표지 기사." },
  { href: "/lab/f-report", name: "초안 3", direction: "트렌드 리포트형", model: "Fable 5.1", note: "같은 리포트 구조를 다른 팀이 푼 안." },
  { href: "/lab/f-editorial", name: "초안 4", direction: "에디토리얼형", model: "Fable 5.1", note: "같은 잡지 구조를 다른 팀이 푼 안." },
  { href: "/lab/t-studio", name: "초안 5", direction: "마케터 스튜디오형", model: "팀원 기획 + Opus 5.5", note: "우리 브랜드 기준 이번 주 할 일 → 근거 → 상품 한 줄로 쇼츠 제작 키트까지. 예시 데이터로만 돈다(실데이터 아님).", samples: false },
];
const SAMPLES = [
  { id: "t_wonyoung", label: "원영적 사고" },
  { id: "t_oshikatsu", label: "推し活", lang: "ja" },
];
const CHECK = [
  "처음 온 마케터가 10초 안에 '이번 주 내 시장에서 뭘 쓰면 되나'를 알 수 있나",
  "다시 오고 싶은 이유가 있나 — 지난번 이후 바뀐 것, 관심 밈, 이번 주 소식",
  "숫자와 그래프가 믿음이 가나 — 없는 데이터를 있는 것처럼 보이지 않나",
  "업종과 상관없이 어느 회사에서 써도 어색하지 않나",
  "휴대폰에서도 읽기 편한가",
];

export default function LabIndex() {
  return (
    <main id="main" className="mx-auto max-w-[880px] px-5 py-12 sm:px-8 sm:py-16">
      <h1 className="text-[28px] font-semibold tracking-[-0.01em] text-[#17191C]">디자인 초안</h1>
      <p className="mt-3 max-w-[640px] text-[15px] leading-[1.6] text-[#4B525C]">
        같은 실데이터로 만든 초안 넷, 예시 데이터로 도는 초안 하나(초안 5)와 지금 화면입니다. 초안마다 첫 화면과 밈 항목 화면이 있고, 휴대폰 폭에서도 볼 수 있습니다.
        마음에 드는 초안과 그 이유를 알려 주세요.
      </p>

      <ul className="mt-10 divide-y divide-[#E4E7EB] border-y border-[#E4E7EB]">
        {DRAFTS.map((d) => (
          <li key={d.href} className="grid gap-3 py-6 sm:grid-cols-[1fr_auto] sm:items-center">
            <div>
              <p className="text-[18px] font-semibold text-[#17191C]">{d.name} <span className="font-normal text-[#4B525C]">{d.direction}</span></p>
              <p className="mt-1 text-[14px] text-[#646B76]">{d.model}</p>
              <p className="mt-2 text-[15px] leading-[1.55] text-[#4B525C]">{d.note}</p>
            </div>
            <div className="flex flex-wrap gap-2 sm:justify-end">
              <Link href={d.href} className="inline-flex h-10 items-center rounded-md bg-[#17191C] px-4 text-[14px] font-medium text-white hover:bg-[#17191C]/85">첫 화면</Link>
              {d.samples !== false && SAMPLES.map((s) => (
                <Link key={s.id} href={`${d.href}/m/${s.id}`} className="inline-flex h-10 items-center rounded-md border border-[#CBD0D6] px-3 text-[14px] text-[#17191C] hover:border-[#17191C]">
                  <span lang={s.lang}>{s.label}</span>
                </Link>
              ))}
            </div>
          </li>
        ))}
        <li className="grid gap-3 py-6 sm:grid-cols-[1fr_auto] sm:items-center">
          <div>
            <p className="text-[18px] font-semibold text-[#17191C]">지금 화면</p>
            <p className="mt-2 text-[15px] leading-[1.55] text-[#4B525C]">비교용. 지금 운영 중인 화면(표 중심)입니다.</p>
          </div>
          <div className="flex flex-wrap gap-2 sm:justify-end">
            <Link href="/" className="inline-flex h-10 items-center rounded-md border border-[#CBD0D6] px-4 text-[14px] text-[#17191C] hover:border-[#17191C]">첫 화면</Link>
            <Link href="/dictionary/t_wonyoung" className="inline-flex h-10 items-center rounded-md border border-[#CBD0D6] px-3 text-[14px] text-[#17191C] hover:border-[#17191C]">원영적 사고</Link>
          </div>
        </li>
      </ul>

      <h2 className="mt-12 text-[18px] font-semibold text-[#17191C]">볼 때 이것만 봐 주세요</h2>
      <ol className="mt-4 list-decimal space-y-2 pl-5 text-[15px] leading-[1.6] text-[#4B525C]">
        {CHECK.map((c) => <li key={c}>{c}</li>)}
      </ol>
    </main>
  );
}
