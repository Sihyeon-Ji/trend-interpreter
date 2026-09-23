import { ReviewTable } from "@/components/review-table";
import { getReviewQueue, getReviewStats, isSampleMode } from "@/lib/data";

export default async function AdminReviewPage() {
  const [items, stats] = await Promise.all([getReviewQueue(), getReviewStats()]);
  const total = stats.verified_auto + stats.verified_human + stats.needs_review + stats.rejected;
  const pct = (n: number) => (total ? Math.round((n / total) * 100) : 0);
  return (
    <section className="space-y-4">
      <p className="text-[15px] text-charcoal">
        근거가 규칙을 통과한 뜻은 사람 손 없이 사전에 실립니다. 지금까지 <span className="font-medium text-ink">자동 확인 {stats.verified_auto}건({pct(stats.verified_auto)}%)</span>, 검수로 확인 {stats.verified_human}건, 검수 대기 {stats.needs_review}건, 제외 {stats.rejected}건입니다.
        아래는 규칙에 걸려 사람이 봐야 하는 {items.length}건입니다. 승인한 뜻만 사전에 실리고, 결정은 기록으로 남습니다.
      </p>
      <ReviewTable items={items} live={!isSampleMode} />
    </section>
  );
}
