# Echo PMO – environment checklist (competition setup: straight to Gemini)

Goal: **an agent that manages a project by connecting the tools work actually happens in.**
Built exactly as it will be submitted.

```
user / event → [our agent service · FastAPI]
                   ├─ Gemini (function calling) : decides what to do and explains it
                   └─ tool adapters (our code)
                        ├─ Jira Cloud REST v3   (API token, sandbox site)
                        ├─ Kaneo (self-hosted)  (optional, stage 2)
                        └─ the schedule engine  (pure Python: CPM, delay forecast)
```

Two rules:
1. **Code computes the numbers and the schedule; Gemini only reads, judges and explains.**
2. **Writes go to the sandbox only.** The company's live Jira is not even read here.

---

## 0. Where things stand (updated 2026-09-20)

| item | state | note |
|---|---|---|
| Node.js / npm | ✅ v24.11.1 / 11.11.1 | |
| Python | ✅ 3.12 | |
| Docker | ✅ 29.8.0 | installed |
| gcloud CLI | ❌ not installed | needed for the Cloud Run deploy |
| `GEMINI_API_KEY` | ✅ issued and verified | model is `gemini-3.6-flash` |
| Jira sandbox + API token | ✅ `dmswisl1017.atlassian.net` / `ECHO` | 40 seeded issues created |
| ⚠️ note | this PC's Claude has a connector to `cytur.atlassian.net` (live) | **not used by this project.** The code carries a domain guard |

### Implementation status

| step | what | state |
|---|---|---|
| 2-1 | environment check (`tools/check_env.py`) | ✅ everything OK |
| 2-2 | 40 demo issues (`seeds/board.py`, `seeds/jira_seed.py`) | ✅ created in Jira |
| 2-3 | the schedule engine (`schedule.py`) | ✅ tests pass |
| 2-3+ | **resource-constrained scheduling (`capacity.py`)** | ✅ the differentiator |
| 2-4 | the Gemini tool layer (`tools.py`) | ✅ 6 reads + 3 write proposals |
| 2-5 | the PMO loop and weekly report | ✅ one full pass |
| 2-5+ | multimodal input (`ingest.py`) | ✅ verified (synthetic image) |
| 2-5+ | the approval gate (`approve.py`) | ✅ with an audit log |
| 2-5+ | web service and demo UI (`api.py`) | ✅ Dockerfile included |
| 2-6 | Cloud Run deploy + Vertex AI switch | ⏳ needs a GCP project |

For how to use it, see [README.md](README.md).

> This project was moved into the team repository at `prototype/pmo-agent/`.
> Every path below is relative to that directory.

---

## 1. What has to be created by hand (accounts and keys are a person's job)

### 1-1. Gemini API key ⭐ required · 2 minutes
- [ ] https://aistudio.google.com/apikey → **Create API key**
- [ ] save `GEMINI_API_KEY=...` in `prototype/pmo-agent/.env` (copy `.env.example`)
- [ ] the free tier is enough for development

### 1-2. Jira sandbox site + API token ⭐ required · 10 minutes
- [ ] create a **new site** at https://www.atlassian.com/software/jira/free
      - example site name: `echo-pmo-demo` → `echo-pmo-demo.atlassian.net`
      - **use an email other than the work account** – keeps it away from org policy and real data
      - the free plan (10 users)
- [ ] create a project: **Team-managed / Software / Scrum**, key `ECHO`
- [ ] issue an API token: https://id.atlassian.com/manage-profile/security/api-tokens →
      **Create API token**
- [ ] save in `.env`:
      ```
      JIRA_SITE=echo-pmo-demo.atlassian.net
      JIRA_EMAIL=<the email the site was created with>
      JIRA_API_TOKEN=<the token>
      JIRA_PROJECT_KEY=ECHO
      ```

> With that much, the whole core loop can be verified: detect → cause → propose → approve →
> update the ticket → report.

### 1-3. Google Cloud project – a competition requirement · 20 minutes (by two weeks before submission)
- [ ] https://console.cloud.google.com → create a project (e.g. `echo-pmo-2026`)
- [ ] attach a billing account ($300 of free credit)
- [ ] enable the APIs: **Cloud Run, Artifact Registry, Vertex AI, Secret Manager**
- [ ] install the `gcloud` CLI → `gcloud auth login`
- [ ] `.env`: `GCP_PROJECT_ID=`, `GCP_REGION=asia-northeast3`
- [ ] for judging credit: switch Gemini calls to go through Vertex AI (key → ADC). Wiring up
      Agent Engine / Agent Platform comes after the demo is finished

### 1-4. Docker Desktop – self-hosting Kaneo (stage 2, optional)
- [ ] install from https://www.docker.com/products/docker-desktop/
- [ ] skippable if the demo stands up on Jira alone. Only needed to show "not tied to one PM tool"

### 1-5. Optional – a free Slack workspace
- [ ] only if reports and approvals should arrive in chat. Skip it if the demo is the web UI

---

## 2. What proceeds automatically once the keys exist (the agent's part)

| order | task | how it is verified |
|---|---|---|
| 2-1 | `python tools/check_env.py` (from prototype/pmo-agent) – key validity, Jira auth and a Gemini function call, all by real calls | everything OK |
| 2-2 | seed the demo project: 40 tasks, 4 owners, dependencies, story points, some slippage | actually created on the Jira board |
| 2-3 | the schedule engine (pure Python): CPM critical path, delay propagation, finish forecast | unit tests |
| 2-4 | the Gemini tool layer: `list_tasks`, `get_task`, `propose_*` – **every write tool sits behind the approval gate** | the tool-call log |
| 2-5 | the PMO loop: detect slip risk → trace the cause → a question for the owner → approve → update the ticket → weekly report | one full pass of the demo scenario |
| 2-6 | Cloud Run deploy + Vertex AI switch | a demo URL |

---

## 3. Safety guards (already in the code)

- [x] a **domain allowlist** in `src/pmo_agent/adapters/jira.py` – a live domain such as
      `cytur.atlassian.net` raises
- [x] write functions default to `dry_run=True` and cannot run without approval
- [x] `.gitignore` keeps `.env` out of commits
- [ ] no real names or real customer data in demo data (the seed scripts use fictional people)

---

## 4. What is left

1-1 (Gemini) and 1-2 (Jira) are done. What remains is deployment.

1. **1-3, the Google Cloud project** – a submission requirement. Install `gcloud`, create the
   project, enable Cloud Run / Vertex AI / Secret Manager
2. switch to `LLM_BACKEND=vertex` and verify against a real call (only the structure exists now)
3. `docker build` → Artifact Registry → Cloud Run deploy → get the demo URL
4. re-check multimodal reading against a photo of real handwriting (only synthetic images so far)

When putting a key in `.env`, never paste the value itself into chat. It goes in the file only.
