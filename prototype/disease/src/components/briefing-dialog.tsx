"use client";

import { useState } from "react";
import {
  ArrowUpRight,
  Check,
  Download,
  LoaderCircle,
  FileText,
  FileSearch,
  ArrowRight,
} from "lucide-react";
import Dialog from "./dialog";
import type { Briefing, Filters, Report } from "@/lib/types";
import { formatDate } from "@/lib/selectors";

function exportBrief(brief: Briefing) {
  const sections = [
    ["Observations", brief.observations],
    ["Conditional scenarios", brief.hypotheses],
    ["Response options", brief.actions],
  ] as const;
  const text = [
    `# ${brief.headline}`,
    `Generated ${brief.generatedAt} · ${brief.mode === "gemini" ? "Gemini analysis" : "Deterministic evidence summary"}`,
    brief.summary,
    ...sections.flatMap(([name, findings]) => [
      `## ${name}`,
      ...findings.map(
        (f) =>
          `### ${f.title}\n${f.detail}\nSources: ${f.reportIds.join(", ")}`,
      ),
    ]),
    "## Limitations",
    ...brief.limitations.map((item) => `- ${item}`),
    "## Sources",
    ...brief.evidence.map(
      (r) =>
        `- ${r.id}: [${r.title}](${r.url}) · ${r.sourceId.toUpperCase()} · ${r.publishedAt}`,
    ),
  ].join("\n\n");
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/markdown;charset=utf-8" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `outbreak-atlas-brief-${brief.generatedAt.slice(0, 10)}.md`;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function BriefingDialog({
  filters,
  count,
  aiEnabled,
  accessTokenRequired,
  onClose,
  onReport,
  embedded = false,
}: {
  embedded?: boolean;
  filters: Filters;
  count: number;
  aiEnabled: boolean;
  accessTokenRequired: boolean;
  onClose: () => void;
  onReport: (report: Report) => void;
}) {
  const [question, setQuestion] = useState(
    "What should a public-health analyst review first? Connect the evidence, explain what remains unknown, and identify official response options.",
  );
  const [token, setToken] = useState("");
  const [brief, setBrief] = useState<Briefing | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function generate() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/briefing", {
        method: "POST",
        signal: AbortSignal.timeout(110_000),
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ filters, question }),
      });
      const result = await response.json();
      if (!response.ok)
        throw new Error(result.error || "Analysis could not be completed.");
      setBrief(result);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Connection failed. Please retry.",
      );
    } finally {
      setLoading(false);
    }
  }

  const content = (
    <>
      {!brief ? (
        <>
          <div className="brief-icon">
            <FileText size={25} />
          </div>
          <span className="eyebrow">ANALYSIS / REPORT GENERATOR</span>
          <h2>Prepare a situation report.</h2>
          <p className="dialog-description">
            {aiEnabled
              ? "An evidence agent will read official assessments, compare reporting coverage, and check source freshness before preparing your brief."
              : "Create a source-linked coverage summary from the current view. Narrative risk analysis becomes available when Gemini is connected."}
          </p>
          <div className="brief-context">
            <span className="dot teal" /> {count} matching reports{" "}
            <span>·</span> Past {filters.days} days <span>·</span>{" "}
            {filters.disease === "all" ? "All disease topics" : filters.disease}
          </div>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void generate();
            }}
          >
            {aiEnabled ? (
              <label className="form-label">
                What would you like to investigate?
                <textarea
                  value={question}
                  maxLength={800}
                  onChange={(event) => setQuestion(event.target.value)}
                  rows={4}
                />
              </label>
            ) : (
              <div className="notice">
                <FileSearch size={18} />
                <div>
                  <strong>Evidence mode</strong>
                  <p>
                    Uses real report metadata and reproducible counts. No AI
                    predictions or generated findings are presented.
                  </p>
                </div>
              </div>
            )}
            {accessTokenRequired ? (
              <label className="form-label">
                Analysis access token
                <input
                  type="password"
                  autoComplete="off"
                  value={token}
                  required
                  onChange={(event) => setToken(event.target.value)}
                />
              </label>
            ) : null}
            <div className="agent-flow">
              <span>
                <FileSearch size={15} /> Retrieve
              </span>
              <ArrowRight size={13} />
              <span>Compare</span>
              <ArrowRight size={13} />
              <span>Check evidence</span>
              <ArrowRight size={13} />
              <span>Brief</span>
            </div>
            {error ? (
              <p className="error-message" role="alert">
                {error}
              </p>
            ) : null}
            <button
              className="button primary full-width"
              disabled={loading || count === 0}
              type="submit"
            >
              {loading ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <FileText size={17} />
              )}
              {loading
                ? "Reviewing selected evidence…"
                : aiEnabled
                  ? "Generate AI report"
                  : "Generate report"}
            </button>
            <p className="small-note">
              {aiEnabled
                ? "Analysis may take up to 90 seconds. All findings include source references."
                : "The summary reflects reporting activity, not disease incidence."}
            </p>
          </form>
        </>
      ) : (
        <>
          <div className="brief-result-meta">
            <span className="status-pill">
              <span className="dot teal" />
              {brief.mode === "gemini" ? "GEMINI ANALYSIS" : "EVIDENCE SUMMARY"}
            </span>
            <button
              className="button subtle"
              onClick={() => exportBrief(brief)}
            >
              <Download size={15} /> Export brief
            </button>
          </div>
          <h2>{brief.headline}</h2>
          <p className="dialog-description">{brief.summary}</p>
          <div className="completed-steps">
            {brief.steps.map((step, index) => (
              <span key={index}>
                <Check size={13} />
                {step}
              </span>
            ))}
          </div>
          {(
            [
              ["01", "Observed evidence", brief.observations],
              ["02", "Conditional scenarios · not forecasts", brief.hypotheses],
              ["03", "Response & review options", brief.actions],
            ] as const
          ).map(([number, label, findings]) => (
            <section className="brief-section" key={number}>
              <h3>
                <span>{number}</span>
                {label}
              </h3>
              {findings.length ? (
                findings.map((finding, index) => (
                  <article className="finding" key={index}>
                    <h4>{finding.title}</h4>
                    <p>{finding.detail}</p>
                    <div className="citation-row">
                      {finding.reportIds.map((id) => {
                        const report = brief.evidence.find((r) => r.id === id);
                        return report ? (
                          <button
                            key={id}
                            className="citation"
                            onClick={() => onReport(report)}
                          >
                            {report.sourceId.toUpperCase()} ·{" "}
                            {formatDate(report.publishedAt)}
                            <ArrowUpRight size={12} />
                          </button>
                        ) : null;
                      })}
                    </div>
                  </article>
                ))
              ) : (
                <p className="small-note">
                  No scenarios generated. The evidence summary does not infer
                  future outbreaks.
                </p>
              )}
            </section>
          ))}
          <section className="limitations">
            <h3>What this brief cannot establish</h3>
            <ul>
              {brief.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        </>
      )}
    </>
  );
  return embedded ? (
    <section className="report-composer">{content}</section>
  ) : (
    <Dialog title="Intelligence briefing" wide onClose={onClose}>
      {content}
    </Dialog>
  );
}
