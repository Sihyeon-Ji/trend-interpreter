# Outbreak Atlas

A working public-health intelligence prototype for the Google Cloud AI Builder Cup 2026. It combines selected official disease reports, a terrain-textured 3D Earth, publication playback, an illustrative scenario laboratory, and a source-grounded Gemini investigation agent.

The interface is organized into three workspaces: **Dashboard**, **Diseases & scenarios**, and **Reports**. A black and crimson theme uses one unified header and a fixed, borderless globe canvas. Region summaries, disease dossiers, and scenario controls open on hover or explicit activation; no permanent side panels reduce the globe area. Touch users open and dismiss these overlays with buttons. The terrain color is thematic, while hatched regions represent report coverage.

## Run locally

Requires Node.js 24 or later and npm.

```sh
npm ci
npm run dev
```

Open http://localhost:3000. No API key is required for data collection, filtering, bookmarking, exports, or deterministic evidence briefs.

For a production build:

```sh
npm run build
npm start
```

The production start script prepares the standalone server assets and reads `.env.local` when present. Use `PORT=3100 npm start` to change the port. Data and analysis run on the server; credentials are never included in client bundles.

## Connect Gemini

Copy `.env.example` to `.env.local`, set `GEMINI_API_KEY` to a Gemini API key, and restart the server. The default model is `gemini-3.8-flash`; `GEMINI_MODEL` may select another model supporting function calling and JSON-schema output. Keys are not entered into the web UI or stored in browser storage.

When configured, the agent selects at most 24 reports from the current filters and can call three read-only tools:

- `read_report` reads an indexed report, including available official assessment and advice.
- `compare_coverage` compares publication counts by disease and source.
- `check_source_health` checks collection dates, publication dates, and missing feeds.

Investigation is limited to three tool rounds, four calls per round, and an 80-second overall model timeout. A final structured response separates observations, conditional scenarios, response options, and limitations. Invalid output or citations outside the selected evidence set fail the request. Citation validation is not semantic fact-checking; users must inspect original reports.

Without a key, the interface explicitly labels **Evidence mode** and generates a deterministic report-count summary. It does not simulate AI analysis or prediction. Actual Gemini service execution requires a valid key and model access; the keyless workflow and mocked tool/validation paths are tested separately.

## Data and coverage

| Source | Collection                                              | Scope                                         |
| ------ | ------------------------------------------------------- | --------------------------------------------- |
| WHO    | Disease Outbreak News JSON API, latest 100 publications | Selected global acute public-health events    |
| CDC    | Travel Health Notices RSS                               | Destination-specific public-health notices    |
| ECDC   | Communicable Disease Threats Report RSS                 | Weekly multi-disease bulletins                |
| UKHSA  | GOV.UK official news Atom feed                          | Agency news and public-health reporting       |
| KDCA   | Advertised official press-release RSS                   | Currently returns an unsupported-feed message |

Official references:

- [WHO Disease Outbreak News](https://www.who.int/emergencies/disease-outbreak-news)
- [CDC RSS documentation](https://wwwnc.cdc.gov/travel/page/rss)
- [ECDC RSS feeds](https://www.ecdc.europa.eu/en/rss-feeds)
- [UKHSA news](https://www.gov.uk/search/news-and-communications?organisations%5B%5D=uk-health-security-agency)
- [KDCA RSS directory](https://www.kdca.go.kr/kdca/4912/subview.do)
- [Gemini models](https://ai.google.dev/gemini-api/docs/models)
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)

The initial capture contains 153 real source records retrieved on 2026-09-16. Raw summaries and advice are plain-text extracts and may be truncated; source links point to the authoritative originals. Disease tags are deterministic matches in titles and summaries, not validated clinical classifications. Country shading reflects matches in titles, not measured infection boundaries. Regional and global reports without explicit country names remain accessible in the report list.

Each process caches parallel collections for 15 minutes and deduplicates concurrent refreshes. The open browser polls on the same interval. Manual refresh returns the latest available cache; it does not bypass the upstream collection limit. There is no background ingestion while the app is closed or a Cloud Run instance is idle.

If a source fails, its previous successful in-memory capture is used, or the bundled official capture if available. The UI shows **Stored capture** and preserves the original retrieval time. A source without usable stored records is **Unavailable**, never silently represented as live.

Update the bundled capture explicitly:

```sh
npm run snapshot
```

This replaces `src/data/snapshot.json` with actual results and source statuses. It does not generate synthetic outbreak data.

## What the prototype establishes

- Rotate and zoom a real 3D Earth, inspect countries, and browse official reports by disease, explicit country name, source, date window, and text.
- View country-shaped report coverage areas instead of point markers. Whole-country shading represents report scope, not measured infection boundaries.
- Play or scrub the observation timeline to show publications available by the selected publication date.
- Open sourced disease profiles and explore an independent, clearly labelled hypothetical expansion scenario.
- Review weekly publication counts, compare disease coverage, and open full original sources.
- Save report IDs locally in the browser and download filtered JSON or a cited Markdown brief.
- Inspect source health, timestamps, and missing coverage.
- Investigate selected reports using Gemini when configured.

Publication counts are not case counts, incidence, transmission rates, or measures of risk. Reporting volume may reflect repeated updates, policy news, or changed surveillance. Disease co-mentions do not establish epidemiological relationships. The dataset is a limited moving window, not a comprehensive national surveillance database. Older bookmarks can outlive that window and are shown only when their records remain in the loaded collection and match the selected filters.

The prototype does not predict the next COVID-19, produce calibrated pandemic probabilities, diagnose patients, or replace public-health guidance. Gemini scenarios are conditional hypotheses with evidence gaps, not validated forecasts. No patient-level or personal health data is collected.

## Scenario laboratory

The scenario view is a local, deterministic visualization and works without an LLM key. Choose a disease for reference context, choose a starting country, and adjust visual expansion pace and response strength. Play, pause, reset, or scrub a 60-day hypothetical timeline. Export the settings and model description as JSON.

The nominal angular radius begins at 2 degrees and grows by 0.35, 0.65, or 1 degree per hypothetical day. A response assumption from 0 to 100 reduces that illustrative growth by up to 70 percent. A fixed contour variation softens the envelope shape, and the colored fill is clipped to land. These are visual parameters, not calibrated transmission or intervention-effectiveness estimates. The profile selection does not change disease-specific model parameters. No mobility network, population, case count, epidemiological reproduction number, or future infection estimate is used.

The observation layer and scenario layer are mutually exclusive. A scenario envelope is never added to the official-source evidence provided to the report agent. Disease reference profiles cite WHO directly. Systems without WebGL use an orthographic, rotatable geographic fallback; the selectors and scenario controls remain available.

## Verification

```sh
npm test
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

Unit tests cover feed formats, source URL restrictions, invalid dates, overlapping country names, filtering, stale-data fallback, cache deduplication, evidence limits, agent tool boundaries, citation validation, request validation, access control, throttling, and scenario controls. Browser tests cover WebGL terrain rendering, country selection, observation playback, scenario playback and parameter changes, WebGL fallback, persistent bookmarks, source details, export, source gaps, brief citations, and mobile overflow. Browser tests use Chromium's software graphics renderer for reproducible WebGL support. Screenshots are written to `artifacts/`.

## Cloud Run container

```sh
docker build -t outbreak-atlas .
docker run --rm -p 8080:8080 --env-file .env.local outbreak-atlas
```

To use keyless evidence mode, omit `--env-file .env.local`. The container runs as a non-root user, listens on `PORT`, and exposes `/api/health`.

For Cloud Run, build a Linux AMD64 image, including when developing on Apple Silicon:

```sh
docker build --platform linux/amd64 -t outbreak-atlas:cloud-run .
```

The project is ready for Cloud Run container deployment but does not create a cloud project, publish a service, or provision credentials automatically. Use a dedicated runtime service account and Secret Manager for `GEMINI_API_KEY` and, when used, `ANALYSIS_ACCESS_TOKEN`. Keep the service IAM-protected for a private demo. For public access, protect paid analysis with `ANALYSIS_ACCESS_TOKEN`, enforce provider quotas, and apply an edge-level request limit. The local one-at-a-time guard and ten-second cooldown are per-process, not distributed abuse protection. An access token is held only in the active briefing form and sent in an authorization header; it is not stored persistently.

## Project layout

```text
src/app/                Next.js page, styles, and server API routes
src/components/         Observatory UI, Three.js globe, reports, and briefing UI
src/lib/sources.ts      Official-source adapters and normalization
src/lib/dataset.ts      Collection, cache, and stale-source fallback
src/lib/classify.ts     Disease/topic matching and country-title extraction
src/lib/agent.ts        Bounded Gemini tool loop
src/lib/briefing.ts     Evidence selection and output validation
src/lib/scenario.ts     Explicitly hypothetical visual expansion parameters
src/lib/diseases.ts     WHO-linked disease reference profiles
src/data/               Captured official reports and generated map geometry
scripts/                Snapshot, map generation, and production start
tests/                  Data, validation, and API tests
e2e/                    Browser workflow tests
```

World boundaries use the Natural Earth geometry distributed by `world-atlas`; country names and coordinates come from `world-countries`. Run `npm run map` to regenerate the geographic features and country index. The globe uses [NASA Blue Marble land/ocean/ice imagery](https://visibleearth.nasa.gov/images/57730/the-blue-marble-land-surface-ocean-color-and-sea-ice), stored locally in `public/earth-day.jpg`. No external tile service or map API key is needed. Boundaries are for visualization and imply no position on territorial status.

The Perplexity link provided during project setup could not be accessed (HTTP 403), so its contents are not represented as verified requirements.
