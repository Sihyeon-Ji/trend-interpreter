"use client";

import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from "react";
import dynamic from "next/dynamic";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Biohazard,
  Bookmark,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Crosshair,
  Database,
  Eye,
  EyeOff,
  FileText,
  Globe2,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  X,
} from "lucide-react";
import Dialog from "./dialog";
import ContextPopover from "./context-popover";
import ReportDetail from "./report-detail";
import BriefingDialog from "./briefing-dialog";
import countryIndex from "@/data/country-index.json";
import {
  DEFAULT_FILTERS,
  DAY_MS,
  diseaseCounts,
  filterReports,
  formatDate,
  weeklyCounts,
} from "@/lib/selectors";
import { DISEASE_PROFILES } from "@/lib/diseases";
import {
  SCENARIO_DAYS,
  SCENARIO_METHOD,
  scenarioRadius,
  type ScenarioPace,
} from "@/lib/scenario";
import type { Country, Dataset, Filters, Report } from "@/lib/types";

const EarthGlobe = dynamic(() => import("./earth-globe"), {
  ssr: false,
  loading: () => (
    <div className="globe-loading">
      LOADING EARTH VIEW
      <span />
    </div>
  ),
});
type View = "dashboard" | "scenarios" | "reports";
const REFRESH_INTERVAL_MS = 15 * 60 * 1000;
const WATCHLIST_KEY = "outbreak-atlas:watchlist:v1";
const INITIAL_ORIGIN = countryIndex.find(
  (country) => country.code === "CD",
) as Country;
const sourceNames: Record<string, string> = {
  who: "WHO",
  cdc: "CDC",
  ecdc: "ECDC",
  ukhsa: "UKHSA",
  kdca: "KDCA",
};

function downloadJson(value: unknown, filename: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function Dashboard({
  initialDataset,
  aiEnabled: initialAiEnabled,
  accessTokenRequired: initialTokenRequired,
}: {
  initialDataset: Dataset;
  aiEnabled: boolean;
  accessTokenRequired: boolean;
}) {
  const [dataset, setDataset] = useState(initialDataset);
  const [aiEnabled, setAiEnabled] = useState(initialAiEnabled);
  const [tokenRequired, setTokenRequired] = useState(initialTokenRequired);
  const [view, setView] = useState<View>("dashboard");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [showSources, setShowSources] = useState(false);
  const [showMethod, setShowMethod] = useState(false);
  const [savedIds, setSavedIds] = useState<string[]>([]);
  const [savedOnly, setSavedOnly] = useState(false);
  const [notice, setNotice] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [coverage, setCoverage] = useState(true);
  const [observationDay, setObservationDay] = useState(DEFAULT_FILTERS.days);
  const [scenarioDay, setScenarioDay] = useState(0);
  const [pace, setPace] = useState<ScenarioPace>("baseline");
  const [responseStrength, setResponseStrength] = useState(30);
  const [origin, setOrigin] = useState<Country>(INITIAL_ORIGIN);
  const [playing, setPlaying] = useState(false);
  const [reportLimit, setReportLimit] = useState(20);
  const search = useDeferredValue(filters.search);
  const now = Date.parse(dataset.collectedAt);
  const scenarioMode = view === "scenarios";
  const endDay = scenarioMode ? SCENARIO_DAYS : filters.days;
  const day = scenarioMode ? scenarioDay : observationDay;

  useEffect(() => {
    try {
      const saved: unknown = JSON.parse(
        localStorage.getItem(WATCHLIST_KEY) || "[]",
      );
      if (Array.isArray(saved))
        setSavedIds(
          saved
            .filter((id): id is string => typeof id === "string")
            .slice(0, 200),
        );
    } catch {
      /* Bookmarks can still be used without persistent browser storage. */
    }
    function focusSearch(event: KeyboardEvent) {
      if (
        event.key !== "/" ||
        event.metaKey ||
        event.ctrlKey ||
        /INPUT|TEXTAREA|SELECT/.test((event.target as HTMLElement)?.tagName)
      )
        return;
      const input = document.querySelector<HTMLInputElement>(
        'input[aria-label="Search reports"]',
      );
      if (input) {
        event.preventDefault();
        input.focus();
      }
    }
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const response = await fetch("/api/reports", {
        signal: AbortSignal.timeout(20_000),
      });
      if (!response.ok) throw new Error();
      const data = await response.json();
      setDataset(data);
      setAiEnabled(data.aiEnabled);
      setTokenRequired(data.accessTokenRequired);
      setNotice(
        "Latest available collection loaded. Source checks are cached for 15 minutes.",
      );
    } catch {
      setNotice(
        "Collection could not be refreshed. Previously retrieved reports remain visible.",
      );
    } finally {
      setRefreshing(false);
    }
  }, []);
  useEffect(() => {
    const timer = setInterval(() => {
      void refresh();
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    if (!playing || view === "reports") return;
    const timer = setInterval(
      () => {
        if (scenarioMode)
          setScenarioDay((current) => Math.min(SCENARIO_DAYS, current + 1));
        else
          setObservationDay((current) => Math.min(filters.days, current + 1));
      },
      scenarioMode ? 240 : 100,
    );
    return () => clearInterval(timer);
  }, [playing, scenarioMode, filters.days, view]);
  useEffect(() => {
    if (day >= endDay) setPlaying(false);
  }, [day, endDay]);

  const allWindowReports = useMemo(
    () =>
      filterReports(
        dataset.reports,
        { ...filters, search, country: "all" },
        now,
      ),
    [dataset.reports, filters, search, now],
  );
  const throughDate = now - (filters.days - observationDay) * DAY_MS;
  const observed = useMemo(
    () =>
      allWindowReports.filter(
        (report) => Date.parse(report.publishedAt) <= throughDate,
      ),
    [allWindowReports, throughDate],
  );
  const focusedReports = useMemo(
    () =>
      filterReports(
        view === "dashboard" ? observed : allWindowReports,
        { ...filters, search },
        now,
      ),
    [observed, allWindowReports, filters, search, now, view],
  );
  const diseases = diseaseCounts(allWindowReports);
  const diseaseOptions = [
    ...new Set([
      ...diseaseCounts(dataset.reports).map((item) => item.name),
      ...DISEASE_PROFILES.map((item) => item.name),
    ]),
  ].sort();
  const locations = useMemo(() => {
    const counts = new Map<string, { country: Country; count: number }>();
    for (const report of observed)
      for (const country of report.countries)
        counts.set(country.code, {
          country,
          count: (counts.get(country.code)?.count ?? 0) + 1,
        });
    return [...counts.values()].sort((a, b) => b.count - a.count);
  }, [observed]);
  const selectedCountry = countryIndex.find(
    (country) => country.code === filters.country,
  );
  const liveSources = dataset.sources.filter(
    (source) => source.status === "live",
  ).length;
  const chart = weeklyCounts(allWindowReports, filters.days, now);
  const chartMax = Math.max(1, ...chart.map((item) => item.count));
  const profile = DISEASE_PROFILES.find(
    (item) => item.name === filters.disease,
  );
  const scenario = useMemo(
    () => ({ day: scenarioDay, pace, response: responseStrength, origin }),
    [scenarioDay, pace, responseStrength, origin],
  );
  const archive = savedOnly
    ? focusedReports.filter((report) => savedIds.includes(report.id))
    : focusedReports;

  function changeView(next: View) {
    setView(next);
    setPlaying(false);
    if (next === "scenarios" && filters.disease === "all")
      setFilters((current) => ({
        ...current,
        disease: "Ebola",
        country: "all",
      }));
    if (next === "reports") setObservationDay(filters.days);
  }
  function changeFilters(update: Partial<Filters>) {
    setFilters((current) => ({ ...current, ...update }));
    setReportLimit(20);
    setPlaying(false);
    if (update.days) setObservationDay(update.days);
    if (update.disease) setScenarioDay(0);
  }
  function toggleSave(id: string) {
    const next = savedIds.includes(id)
      ? savedIds.filter((item) => item !== id)
      : [...savedIds, id].slice(-200);
    setSavedIds(next);
    try {
      localStorage.setItem(WATCHLIST_KEY, JSON.stringify(next));
    } catch {
      setNotice("Bookmark saved for this session only.");
    }
  }
  function togglePlayback() {
    if (day >= endDay) {
      if (scenarioMode) setScenarioDay(0);
      else setObservationDay(0);
    }
    setPlaying((value) => !value);
  }
  function resetFilters() {
    setFilters(
      scenarioMode ? { ...DEFAULT_FILTERS, disease: "Ebola" } : DEFAULT_FILTERS,
    );
    setObservationDay(DEFAULT_FILTERS.days);
    setScenarioDay(0);
    setPlaying(false);
  }

  return (
    <div
      className={`operations-app immersive-app ${view === "reports" ? "report-mode" : "globe-mode"}`}
    >
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="unified-header">
        <div className="command-header">
          <a href="/" className="command-brand">
            <span className="brand-mark">
              <Biohazard size={25} strokeWidth={1.4} />
            </span>
            <span>
              OUTBREAK<span className="brand-secondary">ATLAS</span>
              <small>GLOBAL DISEASE OBSERVATORY</small>
            </span>
          </a>
          <nav aria-label="Main navigation" className="command-nav">
            <button
              aria-label="Dashboard"
              className={view === "dashboard" ? "active" : ""}
              aria-current={view === "dashboard" ? "page" : undefined}
              onClick={() => changeView("dashboard")}
            >
              <span>01</span>
              <Globe2 size={15} />
              Dashboard
            </button>
            <button
              aria-label="Diseases & scenarios"
              className={scenarioMode ? "active" : ""}
              aria-current={scenarioMode ? "page" : undefined}
              onClick={() => changeView("scenarios")}
            >
              <span>02</span>
              <Activity size={15} />
              Diseases & scenarios
            </button>
            <button
              aria-label="Reports"
              className={view === "reports" ? "active" : ""}
              aria-current={view === "reports" ? "page" : undefined}
              onClick={() => changeView("reports")}
            >
              <span>03</span>
              <FileText size={15} />
              Reports
            </button>
          </nav>
          <div className="header-status">
            <button
              onClick={() => setShowSources(true)}
              aria-label="Source connectivity"
            >
              <i
                className={
                  liveSources ? "status-light" : "status-light offline"
                }
              />
              {liveSources}/{dataset.sources.length}
              <span> FEEDS</span>
            </button>
            <button
              className="icon-button"
              aria-label="Methodology"
              onClick={() => setShowMethod(true)}
            >
              <CircleHelp size={17} />
            </button>
          </div>
        </div>
        <div className="workspace-heading">
          <div>
            <p className="eyebrow">
              {view === "dashboard"
                ? "SURVEILLANCE / GLOBAL VIEW"
                : scenarioMode
                  ? "SCENARIO LAB / EXPERIMENTAL"
                  : "INTELLIGENCE / REPORT WORKSPACE"}
            </p>
            <h1>
              {view === "dashboard"
                ? "Global disease monitor"
                : scenarioMode
                  ? "Outbreak scenario lab"
                  : "Reports & analysis"}
            </h1>
          </div>
          <div className="heading-actions">
            <label className="compact-select">
              <span>WINDOW</span>
              <select
                aria-label="Reporting period"
                value={filters.days}
                onChange={(event) =>
                  changeFilters({ days: Number(event.target.value) })
                }
              >
                {[30, 90, 180, 365].map((days) => (
                  <option key={days} value={days}>
                    {days} days
                  </option>
                ))}
              </select>
              <ChevronDown size={12} />
            </label>
            <span className="utc-date">
              {formatDate(dataset.collectedAt, {
                year: "numeric",
              }).toUpperCase()}
              <small>LAST COLLECTION · UTC</small>
            </span>
            <button
              className="icon-button"
              aria-label="Refresh official reports"
              disabled={refreshing}
              onClick={() => {
                void refresh();
              }}
            >
              <RefreshCw size={16} className={refreshing ? "spin" : ""} />
            </button>
          </div>
        </div>
        {notice ? (
          <div className="notice-bar" role="status">
            {notice}
            <button
              className="icon-button"
              aria-label="Dismiss notice"
              onClick={() => setNotice("")}
            >
              <X size={14} />
            </button>
          </div>
        ) : null}
        <div className="filter-strip">
          <label className="search-field">
            <Search size={15} />
            <input
              aria-label="Search reports"
              maxLength={160}
              value={filters.search}
              placeholder="Search reports, regions, diseases"
              onChange={(event) =>
                changeFilters({ search: event.target.value })
              }
            />
            <kbd>/</kbd>
          </label>
          <label className="inline-select">
            <Biohazard size={14} />
            <select
              aria-label="Filter by disease"
              value={filters.disease}
              onChange={(event) =>
                changeFilters({ disease: event.target.value })
              }
            >
              {!scenarioMode ? <option value="all">All diseases</option> : null}
              {diseaseOptions.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
            <ChevronDown size={12} />
          </label>
          {!scenarioMode ? (
            <label className="inline-select">
              <Crosshair size={14} />
              <select
                aria-label="Filter by country"
                value={filters.country}
                onChange={(event) =>
                  changeFilters({ country: event.target.value })
                }
              >
                <option value="all">All regions</option>
                {countryIndex.map((country) => (
                  <option value={country.code} key={country.code}>
                    {country.name}
                  </option>
                ))}
              </select>
              <ChevronDown size={12} />
            </label>
          ) : null}
          <button
            className="filter-reset"
            onClick={resetFilters}
            aria-label="Reset filters"
          >
            <RotateCcw size={13} />
            <span>Reset</span>
          </button>
          <span className="collection-label">
            <i className="status-light" /> OFFICIAL-SOURCE DATA
          </span>
        </div>

        <div className="header-context-bar">
          <div className="header-mode-readout">
            <span className={`layer-badge ${scenarioMode ? "simulation" : ""}`}>
              <span />
              {scenarioMode ? "SIMULATION" : "OBSERVATION"}
            </span>
            <span>
              {scenarioMode
                ? "Illustrative scenario · not a forecast"
                : coverage
                  ? "Country-level report coverage"
                  : "Report layer hidden"}
            </span>
          </div>
          <div className="header-context-tools">
            {view !== "reports" ? (
              <>
                <ContextPopover
                  key={`settings-${view}`}
                  label={scenarioMode ? "Scenario controls" : "Region brief"}
                  icon={
                    scenarioMode ? (
                      <SlidersHorizontal size={14} />
                    ) : (
                      <Crosshair size={14} />
                    )
                  }
                >
                  <div className="peek-content region-peek">
                    {!scenarioMode ? (
                      <>
                        <p className="eyebrow">CURRENT FIELD OF VIEW</p>
                        <h2>{selectedCountry?.name ?? "Worldwide"}</h2>
                        <span className="context-subtitle">
                          {filters.disease === "all"
                            ? "All disease topics"
                            : filters.disease}
                        </span>
                        <div className="field-stat">
                          <strong>
                            {focusedReports.length.toString().padStart(2, "0")}
                          </strong>
                          <span>
                            OFFICIAL
                            <br />
                            PUBLICATIONS
                          </span>
                        </div>
                        <div className="field-ministats">
                          <div>
                            <b>{locations.length}</b>
                            <span>named regions</span>
                          </div>
                          <div>
                            <b>{diseases.length}</b>
                            <span>disease topics</span>
                          </div>
                        </div>
                        <div className="context-divider" />
                        <p className="eyebrow">REGIONS IN THE REPORTS</p>
                        <div className="region-list">
                          {locations.slice(0, 6).map(({ country, count }) => (
                            <button
                              key={country.code}
                              className={
                                filters.country === country.code
                                  ? "selected"
                                  : ""
                              }
                              onClick={() =>
                                changeFilters({
                                  country:
                                    filters.country === country.code
                                      ? "all"
                                      : country.code,
                                })
                              }
                            >
                              <span>{country.name}</span>
                              <b>{count}</b>
                              <ChevronRight size={12} />
                            </button>
                          ))}
                          {!locations.length ? (
                            <p>No country names in this selection.</p>
                          ) : null}
                        </div>
                        <p className="context-note">
                          Shaded regions indicate countries named in reports.
                          They are not measured infection boundaries.
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="eyebrow">SCENARIO CONFIGURATION</p>
                        <h2>{filters.disease}</h2>
                        <span className="context-subtitle">
                          {profile?.family ?? "Official report context"}
                        </span>
                        <label className="scenario-field">
                          Starting region
                          <select
                            aria-label="Scenario origin"
                            value={origin.code}
                            onChange={(event) => {
                              const country = countryIndex.find(
                                (item) => item.code === event.target.value,
                              );
                              if (country) {
                                setOrigin(country);
                                setScenarioDay(0);
                                setPlaying(false);
                              }
                            }}
                          >
                            {countryIndex.map((country) => (
                              <option key={country.code} value={country.code}>
                                {country.name}
                              </option>
                            ))}
                          </select>
                        </label>
                        <div className="scenario-field">
                          Expansion assumption
                          <div
                            className="segmented-control"
                            role="group"
                            aria-label="Expansion pace"
                          >
                            {(["slow", "baseline", "fast"] as const).map(
                              (value) => (
                                <button
                                  key={value}
                                  aria-pressed={pace === value}
                                  className={pace === value ? "selected" : ""}
                                  onClick={() => setPace(value)}
                                >
                                  {value === "slow"
                                    ? "Slower"
                                    : value === "fast"
                                      ? "Faster"
                                      : "Baseline"}
                                </button>
                              ),
                            )}
                          </div>
                        </div>
                        <label className="scenario-field">
                          Response strength <output>{responseStrength}%</output>
                          <input
                            type="range"
                            min="0"
                            max="100"
                            value={responseStrength}
                            aria-label="Response strength"
                            onChange={(event) =>
                              setResponseStrength(Number(event.target.value))
                            }
                          />
                          <span className="range-labels">
                            <span>Limited</span>
                            <span>Strong</span>
                          </span>
                        </label>
                        <div className="scenario-counter">
                          <span>SCENARIO CLOCK</span>
                          <strong>
                            DAY {String(scenarioDay).padStart(2, "0")}
                          </strong>
                          <small>
                            of a {SCENARIO_DAYS}-day hypothetical window
                          </small>
                        </div>
                        <p className="context-note">
                          Visual assumptions only. Disease-specific transmission
                          and intervention effectiveness are not modelled.
                        </p>
                        <button
                          className="text-button"
                          onClick={() =>
                            downloadJson(
                              {
                                disease: filters.disease,
                                ...scenario,
                                method: SCENARIO_METHOD,
                                angularEnvelopeDegrees: scenarioRadius(
                                  scenarioDay,
                                  pace,
                                  responseStrength,
                                ),
                              },
                              "outbreak-atlas-scenario.json",
                            )
                          }
                        >
                          Export scenario settings <ArrowUpRight size={12} />
                        </button>
                      </>
                    )}
                  </div>
                </ContextPopover>
                <ContextPopover
                  key={`info-${view}`}
                  label={scenarioMode ? "Disease dossier" : "Latest reports"}
                  icon={
                    scenarioMode ? (
                      <Biohazard size={14} />
                    ) : (
                      <FileText size={14} />
                    )
                  }
                >
                  <div className="peek-content dossier-peek">
                    {!scenarioMode ? (
                      <>
                        <div className="rail-heading">
                          <span className="eyebrow">INCOMING INTELLIGENCE</span>
                          <span className="count-label">
                            {focusedReports.length}
                          </span>
                        </div>
                        <h2>Latest official reports</h2>
                        <div className="rail-tabs">
                          <span>Most recent</span>
                          <label>
                            <select
                              aria-label="Filter by source"
                              value={filters.source}
                              onChange={(event) =>
                                changeFilters({ source: event.target.value })
                              }
                            >
                              <option value="all">All sources</option>
                              {dataset.sources.map((source) => (
                                <option value={source.id} key={source.id}>
                                  {source.name}
                                </option>
                              ))}
                            </select>
                            <ChevronDown size={10} />
                          </label>
                        </div>
                        <div className="live-report-list">
                          {focusedReports.slice(0, 5).map((report, index) => (
                            <button
                              className="incoming-report"
                              key={report.id}
                              onClick={() => setSelectedReport(report)}
                            >
                              <span className="incoming-meta">
                                <b>{sourceNames[report.sourceId]}</b>
                                <time>{formatDate(report.publishedAt)}</time>
                              </span>
                              <strong>{report.title}</strong>
                              <span className="incoming-bottom">
                                {report.diseases[0] ?? "Public health"}
                                <ArrowUpRight size={12} />
                              </span>
                              <i className={index === 0 ? "new-report" : ""} />
                            </button>
                          ))}
                          {!focusedReports.length ? (
                            <div className="empty-state">
                              <Search size={23} />
                              <h3>No reports in this view</h3>
                              <p>
                                Change the filters or advance the observation
                                timeline.
                              </p>
                              <button
                                className="text-button"
                                onClick={resetFilters}
                              >
                                Reset filters <ArrowRight size={13} />
                              </button>
                            </div>
                          ) : null}
                        </div>
                        <button
                          className="rail-action"
                          onClick={() => changeView("reports")}
                        >
                          Open report workspace <ArrowRight size={14} />
                        </button>
                      </>
                    ) : (
                      <>
                        <div className="rail-heading">
                          <span className="eyebrow">DISEASE DOSSIER</span>
                          <Biohazard size={18} />
                        </div>
                        <h2 className="dossier-title">{filters.disease}</h2>
                        <span className="dossier-family">
                          {profile?.family ?? "Report-based profile"}
                        </span>
                        <section className="dossier-section">
                          <h3>Transmission context</h3>
                          <p className="transmission-route">
                            {profile?.route ??
                              "See current official assessments"}
                          </p>
                          <p>
                            {profile?.summary ??
                              allWindowReports[0]?.summary ??
                              "No matching reports are present in this reporting window. Select another disease or extend the window to review official evidence."}
                          </p>
                        </section>
                        <section className="dossier-section">
                          <h3>Public-health response</h3>
                          {profile ? (
                            <ul>
                              {profile.priorities.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          ) : (
                            <p>
                              Review the source-specific assessment and advice
                              attached to each official report.
                            </p>
                          )}
                        </section>
                        {profile ? (
                          <a
                            className="text-button dossier-source"
                            href={profile.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            WHO disease reference <ArrowUpRight size={12} />
                          </a>
                        ) : null}
                        <div className="dossier-evidence">
                          <span className="eyebrow">
                            EVIDENCE IN THIS COLLECTION
                          </span>
                          <strong>
                            {allWindowReports.length}
                            <span> publications</span>
                          </strong>
                          <p>
                            {
                              new Set(
                                allWindowReports.map(
                                  (report) => report.sourceId,
                                ),
                              ).size
                            }{" "}
                            reporting agencies · past {filters.days} days
                          </p>
                        </div>
                        <button
                          className="rail-action"
                          onClick={() => changeView("reports")}
                        >
                          Create an evidence report <ArrowRight size={14} />
                        </button>
                        <details className="scenario-method">
                          <summary>
                            How this simulation works <ChevronDown size={12} />
                          </summary>
                          <p>{SCENARIO_METHOD}</p>
                        </details>
                      </>
                    )}
                    <button
                      className="source-health"
                      onClick={() => setShowSources(true)}
                    >
                      <span>
                        <Database size={13} />
                        SOURCE CONNECTIVITY
                      </span>
                      <div>
                        {dataset.sources.map((source) => (
                          <span key={source.id}>
                            <i
                              className={`status-light ${source.status !== "live" ? "offline" : ""}`}
                            />
                            {source.name}
                          </span>
                        ))}
                      </div>
                      <small>
                        {liveSources} connected ·{" "}
                        {dataset.sources.length - liveSources} with collection
                        gaps <ArrowUpRight size={11} />
                      </small>
                    </button>
                  </div>
                </ContextPopover>
                {!scenarioMode ? (
                  <button
                    className="hud-trigger"
                    aria-label="Toggle report coverage layer"
                    aria-pressed={coverage}
                    onClick={() => setCoverage(!coverage)}
                  >
                    {coverage ? <Eye size={14} /> : <EyeOff size={14} />}
                    <span>Coverage</span>
                  </button>
                ) : null}
              </>
            ) : null}
            <span className="hud-count">
              {focusedReports.length} reports / {locations.length} regions
            </span>
          </div>
        </div>
      </header>
      <main id="main">
        {view !== "reports" ? (
          <div
            className={`monitor-layout ${scenarioMode ? "scenario-layout" : ""}`}
          >
            <section
              className="planet-stage"
              aria-label={
                scenarioMode ? "Scenario globe" : "Global report coverage"
              }
            >
              <div className="planet-render">
                <EarthGlobe
                  reports={coverage && !scenarioMode ? observed : []}
                  selected={scenarioMode ? origin.code : filters.country}
                  scenario={scenarioMode ? scenario : undefined}
                  onSelect={(country) => {
                    if (scenarioMode) {
                      setOrigin(country);
                      setScenarioDay(0);
                      setPlaying(false);
                    } else
                      changeFilters({
                        country:
                          filters.country === country.code
                            ? "all"
                            : country.code,
                      });
                  }}
                />
              </div>
            </section>

            <section
              className={`timeline-console ${scenarioMode ? "simulation" : ""}`}
              aria-label={
                scenarioMode ? "Scenario playback" : "Publication timeline"
              }
            >
              <div className="playback-control">
                <button
                  className="play-button"
                  aria-label={playing ? "Pause timeline" : "Play timeline"}
                  onClick={togglePlayback}
                >
                  {playing ? (
                    <Pause size={18} fill="currentColor" />
                  ) : (
                    <Play size={18} fill="currentColor" />
                  )}
                </button>
                <button
                  className="icon-button"
                  aria-label="Reset timeline"
                  onClick={() => {
                    setPlaying(false);
                    if (scenarioMode) setScenarioDay(0);
                    else setObservationDay(0);
                  }}
                >
                  <RotateCcw size={16} />
                </button>
                <div>
                  <span className="eyebrow">
                    {scenarioMode ? "SIMULATION TIME" : "REPORTS THROUGH"}
                  </span>
                  <strong>
                    {scenarioMode
                      ? `DAY ${String(scenarioDay).padStart(2, "0")}`
                      : formatDate(new Date(throughDate).toISOString(), {
                          year: "numeric",
                        })}
                  </strong>
                </div>
              </div>
              <div className="timeline-track">
                {!scenarioMode ? (
                  <div
                    className="reporting-bars"
                    aria-label="Weekly publication counts"
                  >
                    {chart.map((item) => (
                      <span
                        key={item.date}
                        title={`${formatDate(item.date)} · ${item.count} publications`}
                        style={{
                          height: `${Math.max(2, (item.count / chartMax) * 100)}%`,
                        }}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="scenario-track-caption">
                    <span>ILLUSTRATIVE EXPANSION</span>
                    <span>
                      {pace.toUpperCase()} PACE / {responseStrength}% RESPONSE
                      ASSUMPTION
                    </span>
                  </div>
                )}
                <input
                  type="range"
                  aria-label={scenarioMode ? "Scenario day" : "Observation day"}
                  min="0"
                  max={endDay}
                  value={day}
                  onChange={(event) => {
                    setPlaying(false);
                    if (scenarioMode)
                      setScenarioDay(Number(event.target.value));
                    else setObservationDay(Number(event.target.value));
                  }}
                />
                <div className="timeline-labels">
                  <span>
                    {scenarioMode
                      ? "DAY 00"
                      : formatDate(
                          new Date(now - filters.days * DAY_MS).toISOString(),
                        )}
                  </span>
                  <span>
                    {scenarioMode
                      ? "DAY 30"
                      : "PUBLICATION DATE · NOT INFECTION DATE"}
                  </span>
                  <span>
                    {scenarioMode ? `DAY ${SCENARIO_DAYS}` : "LATEST"}
                  </span>
                </div>
              </div>
              <div className="timeline-note">
                <span className={scenarioMode ? "simulation-text" : ""}>
                  {scenarioMode ? "SCENARIO MODE" : "OBSERVED REPORTS"}
                </span>
                <small>
                  {scenarioMode
                    ? "Explore assumptions, not predictions"
                    : "Move through the published record"}
                </small>
              </div>
            </section>
          </div>
        ) : (
          <div className="report-workspace">
            <section className="report-archive">
              <div className="archive-heading">
                <div>
                  <p className="eyebrow">SOURCE MATERIAL</p>
                  <h2>
                    Official report archive <span>{focusedReports.length}</span>
                  </h2>
                </div>
                <button
                  className="icon-button"
                  aria-label="Export filtered reports"
                  onClick={() =>
                    downloadJson(
                      {
                        exportedAt: new Date().toISOString(),
                        note: "Official publications, not case counts.",
                        reports: focusedReports,
                      },
                      "outbreak-atlas-reports.json",
                    )
                  }
                >
                  <ArrowDownToLine size={17} />
                </button>
              </div>
              <div className="archive-controls">
                <button
                  className={!savedOnly ? "selected" : ""}
                  onClick={() => setSavedOnly(false)}
                >
                  All reports
                </button>
                <button
                  className={savedOnly ? "selected" : ""}
                  onClick={() => setSavedOnly(true)}
                >
                  <Bookmark size={12} />
                  Saved ({savedIds.length})
                </button>
                <label className="inline-select">
                  <select
                    aria-label="Filter by source"
                    value={filters.source}
                    onChange={(event) =>
                      changeFilters({ source: event.target.value })
                    }
                  >
                    <option value="all">All sources</option>
                    {dataset.sources.map((source) => (
                      <option key={source.id} value={source.id}>
                        {source.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="archive-list">
                {archive.slice(0, reportLimit).map((report) => (
                  <article className="archive-report" key={report.id}>
                    <button
                      onClick={() => setSelectedReport(report)}
                      className="archive-report-main"
                    >
                      <span>
                        <b className={`source-tag ${report.sourceId}`}>
                          {sourceNames[report.sourceId]}
                        </b>
                        <time>
                          {formatDate(report.publishedAt, { year: "numeric" })}
                        </time>
                      </span>
                      <strong>{report.title}</strong>
                      <small>
                        {report.diseases.slice(0, 3).join(" / ") ||
                          "Public health update"}
                      </small>
                    </button>
                    <button
                      className={`icon-button ${savedIds.includes(report.id) ? "bookmarked" : ""}`}
                      aria-label={`${savedIds.includes(report.id) ? "Remove from" : "Add to"} watchlist: ${report.title}`}
                      onClick={() => toggleSave(report.id)}
                    >
                      <Bookmark
                        size={15}
                        fill={
                          savedIds.includes(report.id) ? "currentColor" : "none"
                        }
                      />
                    </button>
                  </article>
                ))}
              </div>
              {!archive.length ? (
                <div className="empty-state">
                  <FileText size={25} />
                  <h3>
                    {savedOnly
                      ? "No saved reports in this view"
                      : "No matching reports"}
                  </h3>
                  <p>Try a broader filter or reporting window.</p>
                </div>
              ) : null}
              {archive.length > reportLimit ? (
                <button
                  className="rail-action"
                  onClick={() => setReportLimit(reportLimit + 20)}
                >
                  Load more reports <ChevronDown size={13} />
                </button>
              ) : null}
            </section>
            <div className="composer-column">
              <BriefingDialog
                key={JSON.stringify(filters)}
                embedded
                filters={filters}
                count={focusedReports.length}
                aiEnabled={aiEnabled}
                accessTokenRequired={tokenRequired}
                onReport={setSelectedReport}
                onClose={() => undefined}
              />
              <div className="report-workspace-note">
                <ShieldCheck size={15} />
                <p>
                  Generated findings retain their source references. Simulation
                  envelopes are not treated as observational evidence.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
      {selectedReport ? (
        <ReportDetail
          report={selectedReport}
          dataset={dataset}
          saved={savedIds.includes(selectedReport.id)}
          onSave={() => toggleSave(selectedReport.id)}
          onClose={() => setSelectedReport(null)}
        />
      ) : null}
      {showSources ? (
        <Dialog
          title="Source connectivity"
          wide
          onClose={() => setShowSources(false)}
        >
          <h2>{liveSources} connected sources</h2>
          <p className="dialog-description">
            Collection times and publication dates are distinct. Unavailable
            sources stay visible.
          </p>
          <div className="source-status-list">
            {dataset.sources.map((source) => (
              <article key={source.id}>
                <div>
                  <span
                    className={`status-light ${source.status === "live" ? "" : "offline"}`}
                  />
                  <strong>{source.name}</strong>
                  <span>
                    {source.status === "live"
                      ? "Connected"
                      : source.status === "snapshot"
                        ? "Stored capture"
                        : "Unavailable"}
                  </span>
                  <b>{source.reportCount} reports</b>
                </div>
                <h3>{source.organization}</h3>
                <p>{source.message}</p>
                <small>
                  Last retrieval:{" "}
                  {source.retrievedAt
                    ? `${formatDate(source.retrievedAt, { year: "numeric", hour: "2-digit", minute: "2-digit" })} UTC`
                    : "No successful collection"}
                </small>
                <a
                  className="text-button"
                  href={source.homepage}
                  target="_blank"
                  rel="noreferrer"
                >
                  Official source <ArrowUpRight size={11} />
                </a>
              </article>
            ))}
          </div>
        </Dialog>
      ) : null}
      {showMethod ? (
        <Dialog title="Methodology" wide onClose={() => setShowMethod(false)}>
          <h2>Reading this observatory</h2>
          <div className="method-sections">
            <section>
              <h3>Observation layer</h3>
              <p>
                Red country regions indicate a country explicitly named in an
                official report title. The entire country is shaded as a report
                footprint because the sources do not provide consistent local
                outbreak boundaries. This is not an infection heatmap. Unmarked
                regions may have disease activity. The timeline replays
                publication dates, not case onset or transmission.
              </p>
            </section>
            <section>
              <h3>Scenario layer</h3>
              <p>{SCENARIO_METHOD}</p>
              <p>
                Disease profiles provide sourced context. Choosing a disease
                does not calibrate the scenario to that disease.
              </p>
            </section>
            <section>
              <h3>Evidence and reporting</h3>
              <p>
                Selected WHO, CDC, ECDC, UKHSA and KDCA feeds are checked at
                most every 15 minutes while the app is used. Failed sources
                retain their original captured dates. This is partial global
                coverage. Gemini findings must cite the supplied evidence set;
                citation validation does not verify the truth of every
                statement.
              </p>
            </section>
            <section>
              <h3>Geographic reference</h3>
              <p>
                Earth imagery comes from NASA’s Blue Marble. Country geometry
                comes from Natural Earth through world-atlas. Country labels and
                reference coordinates come from world-countries. Borders are for
                visualization only.
              </p>
            </section>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}
