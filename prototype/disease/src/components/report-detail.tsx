import { ArrowUpRight, Bookmark, ShieldCheck } from "lucide-react";
import Dialog from "./dialog";
import { formatDate } from "@/lib/selectors";
import type { Dataset, Report } from "@/lib/types";
const SOURCE_LABELS: Record<string, string> = {
  who: "WHO",
  cdc: "CDC",
  ecdc: "ECDC",
  ukhsa: "UKHSA",
  kdca: "KDCA",
};
export default function ReportDetail({
  report,
  dataset,
  saved,
  onSave,
  onClose,
}: {
  report: Report;
  dataset: Dataset;
  saved: boolean;
  onSave: () => void;
  onClose: () => void;
}) {
  const source = dataset.sources.find((s) => s.id === report.sourceId);
  return (
    <Dialog title="Official report" onClose={onClose}>
      <div className="report-meta">
        <span className={`source-tag ${report.sourceId}`}>
          {SOURCE_LABELS[report.sourceId]}
        </span>
        <span>{formatDate(report.publishedAt, { year: "numeric" })}</span>
      </div>
      <h2>{report.title}</h2>
      <div className="tag-row">
        {report.diseases.map((d) => (
          <span className="tag" key={d}>
            {d}
          </span>
        ))}
      </div>
      <p className="report-summary">
        {report.summary ||
          "No summary was provided in the source feed. Open the official report for the full text."}
      </p>
      {report.assessment ? (
        <section className="report-section">
          <h3>Official risk assessment</h3>
          <p>{report.assessment}</p>
        </section>
      ) : null}
      {report.advice ? (
        <section className="report-section">
          <h3>Official advice</h3>
          <p>{report.advice}</p>
        </section>
      ) : null}
      <div className="provenance">
        <ShieldCheck size={19} />
        <div>
          <strong>{source?.organization}</strong>
          <p>
            Published {formatDate(report.publishedAt, { year: "numeric" })} ·{" "}
            {source?.status === "live"
              ? "Retrieved from official feed"
              : "Stored source capture"}
          </p>
          <p>
            Location matches from title:{" "}
            {report.countries.map((c) => c.name).join(", ") ||
              "No country explicitly identified"}
            .
          </p>
          <p>
            Feed extracts may be shortened. The original publication is
            authoritative.
          </p>
        </div>
      </div>
      <div className="dialog-actions">
        <a
          className="button primary"
          href={report.url}
          target="_blank"
          rel="noreferrer"
        >
          Read official report <ArrowUpRight size={16} />
        </a>
        <button className="button" onClick={onSave}>
          <Bookmark size={16} fill={saved ? "currentColor" : "none"} />
          {saved ? "Saved" : "Save report"}
        </button>
      </div>
    </Dialog>
  );
}
