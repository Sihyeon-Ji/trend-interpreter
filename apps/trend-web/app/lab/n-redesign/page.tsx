import type { Metadata } from "next";
import { Who } from "@/components/lab/n-redesign/bits";
import { MakeForm } from "@/components/lab/n-redesign/make-form";

/* 만들기 — 제품·시장·분야·말투를 받는다. 오른쪽 여백은 '누가 무엇을 하나' 를 미리 보여 준다. */
export const metadata: Metadata = { title: "만들기" };

export default function MakePage() {
  return (
    <div className="n-wrap">
      <div className="n-head">
        <h1 className="n-h1">새 캠페인 초안</h1>
        <p className="n-lead" id="n-make-lead">
          제품과 시장을 알려 주면 시장마다 지금 써도 되는 말을 골라 현지어 카피를 씁니다. 모든 초안은 사람이 승인해야 나갑니다.
        </p>
      </div>
      <div className="n-ledger">
        <div><MakeForm /></div>
        <aside className="n-rail" aria-labelledby="n-how">
          <h2 id="n-how">초안이 만들어지는 순서</h2>
          <ol className="n-steps">
            <li><div><Who kind="rule" /><span>그 나라 사전에서 확인된 말 가운데 제품과 맞는 말을 고릅니다. 쓰지 않을 말은 이유와 함께 뺍니다.</span></div></li>
            <li><div><Who kind="model" /><span>고른 말로 Instagram 2개, X 2개 카피를 현지어로 씁니다. 원하면 짧은 영상 대본도.</span></div></li>
            <li><div><Who kind="rule" /><span>쓴 카피를 다시 확인합니다. 사전과 다르게 쓰였거나 식은 말이면 표시합니다.</span></div></li>
            <li><div><Who kind="human" /><span>검수자가 시장마다 승인합니다. 승인한 초안만 복사하고 공유할 수 있습니다.</span></div></li>
          </ol>
        </aside>
      </div>
    </div>
  );
}
