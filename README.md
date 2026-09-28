<img src="docs/brand/logo-full.png" alt="SkillSprint: learn, practice, achieve" width="440">

# SkillSprint AI

Personalised, verifiable onboarding for **Nexora Labs** (TECHWIZ 7 · OnboardVerse · Generative AI PowerPlay).

Admins upload company documents. Deterministic Python extracts every obligation into a **Role Requirement
Matrix**. **Pipeline 1** (Generative AI) writes a staged Day 1 → Day 90 onboarding plan per employee.
**Pipeline 2** (plain Python, no AI) validates that plan against the Matrix. A plan is **Verified** only when
mandatory coverage is 100 %, every source reference is valid and current, and no unresolved contradiction or
unsupported requirement remains.

```
 documents ──► parse + chunk + scan + embed ──► Role Requirement Matrix (Python only)
                                                     │                 │
                         Pipeline 1 (GenAI) ◄────────┘                 │ answer key
                         writes the plan                               ▼
                                 └──────────────► Pipeline 2 (Python only) ──► verification status,
                                                   13 rules, 6 SRS metrics      comparison, review queue
```

## Quick start

Requirements: Docker Desktop, Python 3.12, Node.js 20+.

**One command (Windows):** double-click `start.cmd`, or run `.\start.ps1`. It:

1. Starts Docker Desktop if needed, then the database and the local LLM (on the GPU when there is one).
2. Applies migrations.
3. On a fresh machine only: creates `.env` with a random `SECRET_KEY`, the Python venv, the frontend packages and
   the demo data.
4. Opens the API and web app in their own windows, waits until both are healthy, and opens http://localhost:5173.

It is safe to run again: anything already running is left alone. Options: `-NoLLM`, `-NoBrowser`.
Stop everything with `stop.cmd` or `.\stop.ps1` (`-KeepDocker` stops only the API and web app).

Manual steps, or on macOS/Linux:

```bash
cp .env.example .env            # then set SECRET_KEY (32+ random characters)
docker compose up -d db
python -m venv .venv && .venv\Scripts\activate      # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
alembic upgrade head
python generate_sample_docs.py && python generate_extended_docs.py   # sample corpus (already committed)
python -m scripts.bootstrap_demo --plans            # seed, 39 documents, Matrix, 10 employees, 10 plans
uvicorn src.main:app --reload
```

Open http://localhost:8000/docs, or `api-console.html` in a browser.

Everything in one command (API + database, migrations and seed run on start):

```bash
docker compose --profile app up --build
```

### Logins (seeded)

| Email | Password | Type |
|---|---|---|
| evaluator@nexoralabs.io | `Evaluate@123` | ADMIN (evaluator account) |
| admin@nexoralabs.io | `Admin@123` | ADMIN |
| training@nexoralabs.io | `Train@123` | TRAINING_MANAGER |
| reviewer@nexoralabs.io | `Review@123` | REVIEWER |
| manager@nexoralabs.io | `Manage@123` | MANAGER |
| employee@nexoralabs.io | `Employ@123` | EMPLOYEE (linked to EMP-001, Backend Developer) |

Override the seeded passwords with `SEED_ADMIN_PASSWORD` and `SEED_EVALUATOR_PASSWORD` in production.

### GenAI provider and free fallback

Generation tries providers in order: `GENAI_PROVIDER`, then the fallback chain (default **Gemini, then the local
Ollama model, then offline**).
Each provider gets its own 3-attempt cap, so the chain can never loop. A provider without a key is skipped, and the
reason is recorded. `GET /plans/{id}/generation-run` shows which provider produced the plan
(`provider_chain`, `providers_skipped`, `fell_back`, and a per-attempt `provider`).

| Provider | Cost | Setup |
|---|---|---|
| `anthropic` | paid | `GENAI_API_KEY`; `GENAI_MODEL` defaults to `claude-opus-5` |
| `gemini` (**free fallback**) | free tier | `GEMINI_API_KEY` from https://aistudio.google.com/apikey; model `gemini-3.8-flash` (`GEMINI_MODEL` overrides) |
| `groq`, `openrouter` | free tiers | `GROQ_API_KEY` / `OPENROUTER_API_KEY`. Groq's free tier allows 8K tokens a minute, too small for a full plan prompt |
| `ollama` (**local fallback**) | free, runs on your machine | `docker compose --profile llm up -d` (see below); no key needed |
| `offline` | free | nothing; deterministic, labelled `provider: offline` in every run record |

#### Local LLM on Docker (Ollama)

```bash
docker compose --profile llm up -d                                    # CPU
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile llm up -d   # NVIDIA GPU
```

This starts `skillsprint_ollama` on port 11434. A one-shot `ollama-pull` service then downloads **qwen2.5:3b**
(about 1.9 GB; it fits a 4 GB GPU). Change the model with `OLLAMA_MODEL`. The API finds the server at
`http://localhost:11434/v1`; inside compose, set `OLLAMA_BASE_URL=http://ollama:11434/v1`.

- **No API key is needed.** Ollama has no keys. `OLLAMA_API_KEY` is only sent as a bearer token if you put Ollama
  behind a proxy that asks for one.
- **What it handles:** the context window is 12K tokens (`OLLAMA_CONTEXT_LENGTH`), small enough to keep a
  3B model fully on a 4 GB GPU. At 24K it spills onto the CPU and slows to about 3 tokens/s. Output uses
  schema-constrained decoding (`json_mode: json_schema`), so replies always contain every required field.
  Measured on an RTX 3050 laptop GPU: ping about 1 s once warm, one module rewrite (~6K-token prompt) about 95 s.
- **What it skips:** a full plan prompt is about 37K tokens in and about 45K out. That does not fit, so it is skipped
  at once (`request_too_large`) and the next provider writes the plan.
- **Quality:** a 3B model is weaker than a hosted one and can leave out a requirement. The automatic quality check
  that runs after every rewrite flags any it missed.
- **Timeouts and status:** each local call may take up to 15 minutes (`timeout_seconds: 900`). If the server is
  down, it is skipped without retrying, and AI settings shows "Not running".

The OpenAI-compatible providers share one `httpx` client (`src/genai_pipeline/openai_compat_client.py`), so no
extra SDK is needed. Endpoints and models live in `config/generation.yaml` under `providers`, so a model can be
changed with a config edit. **Note:** on the Gemini free tier, Google may use prompts to improve its products.
Use the paid tier for real company documents.

### Web frontend (React + Vite)

`frontend/` is a React 19 + TypeScript single-page app that drives every API operation. Keys stay on the server;
the browser only calls the API.

```bash
uvicorn src.main:app --port 8000        # API (or scripts\run-api.cmd on Windows)
cd frontend && npm install && npm run dev   # http://localhost:5173 (or scripts\run-web.cmd)
```

Vite proxies `/api/*` to `http://localhost:8000` (set `API_TARGET` to change it). For a static build, run
`npm run build`; `VITE_API_BASE` sets the API URL. Sign in with any demo account on the login screen. The sidebar
shows only the pages that role may use.

| Page | What you can do |
|---|---|
| Plans & AI generation | Generate a plan with AI (choose employee, extra topics, prompt version, simulate a malformed reply); see provider, fallback, attempts and gaps; compare two plans; browse prompt templates |
| Plan detail | Modules, tasks, checklists, quizzes; run validation; GenAI-vs-Python comparison (CSV); the raw AI run (prompt, response, attempts, chain); consistency runs; outdated sources; audit |
| Review queue | Approve, reject, edit, regenerate or comment on findings |
| Documents | Upload (all 9 checks shown), parse, view chunks and traceability, suspicious chunks |
| Semantic search / Requirement Matrix | Query embeddings; build the Matrix in four steps; edit requirements and role mappings |
| Policy updates | Diff versions, list affected plans, dry-run or apply regeneration |
| Validation rules | Toggle and tune the 13 rules, business rules, source contradictions |
| Progress / My onboarding | Live progress, tick off items, take quizzes, record assessments |
| Dashboards / Reports | Per-role statistics; 8 reports with CSV/XLSX/PDF export; record search |
| Organization | Departments, roles (auto-mapped to the Matrix), onboarding stages and durations, employees |
| AI providers | The fallback chain and a live test button for each provider |
| Configuration / Audit | Edit any YAML-backed config as a DB override, reset it, re-rank precedence; view entity history |

## Architecture

| Layer | Folder | Rule |
|---|---|---|
| API | `src/api` | HTTP only; no queries in new routes |
| Services | `src/services` | orchestration; no HTTP objects |
| Repositories | `src/repositories` | all SQL for the new domains |
| Pipeline 1 | `src/genai_pipeline`, `prompt_templates/`, `schemas/` | generates only |
| Pipeline 2 | `src/python_validation`, `src/comparison_engine`, `src/contradiction_checks`, `src/role_matrix` | **no AI import**, enforced by `tests/test_isolation_guard.py` |
| Pure helpers | `src/progress`, `src/impact`, `src/reports`, `src/core/textutil.py` | deterministic |

Nothing an evaluator changes lives in code. Every behaviour is a YAML default under `config/` with a runtime
override stored in `AppConfig` (`GET/PUT/DELETE /config/{key}`):

| Key | Controls |
|---|---|
| `precedence` | document ranks, conflict resolution |
| `requirement_rules` | modal verb families, informational markers, priority signals, competencies, role aliases, topic→department mapping, prerequisite markers |
| `generation` | retrieval floor, retry cap, parameters, prompt version |
| `quiz_types` | allowed quiz types (add one here) |
| `validation_rules` | each Pipeline 2 rule on/off with thresholds; hallucination wording lists; contradiction settings |
| `business_rules` | extra rules checked against generated content |
| `progress` | status thresholds, weak-area signals, recommendation rules |
| `adversarial_patterns` | prompt-injection patterns flagged at parse time |

Roles, departments, stages (onboarding duration), employees and documents are data (`/roles`, `/stages`, …).

## Evaluator walkthrough

Authenticate with `POST /auth/login` and send `Authorization: Bearer <token>`.

| Challenge | How to show it |
|---|---|
| Upload and validate a document | `POST /documents` (nine checks); a renamed .exe, empty file, duplicate or stale version returns 422 with the failing check |
| Parse, chunk, embed | `POST /documents/{id}/parse` (embeds at parse time); `GET /search/coverage` |
| Semantic search, refusal | `GET /search?q=...`; a topic no document covers returns 0 results with `grounded: false` |
| The Matrix | `POST /matrix/extract`, `/matrix/map-roles`, `/matrix/prerequisites`, `/matrix/resolve-conflicts`; `GET /matrix/role/{id}`, `/matrix/summary` (SRS minimums) |
| Why does a requirement apply? | `GET /requirements/{code}`: mapping method and reason per role, source chunk, prerequisites |
| Add a role live | `POST /roles`, then `POST /matrix/map-roles`; the role gets its Matrix with no code change |
| Generate a plan | `POST /plans/generate` (validates immediately); `GET /plans/{id}`; `GET /plans/{id}/generation-run` |
| Hallucination refusal | `POST /plans/generate` with `extra_topics: ["pet insurance"]` records a gap instead of inventing content |
| Retry cap | `POST /plans/generate` with `simulate_malformed: 3` (offline provider) stops after 3 attempts with a structured 502 |
| Pipeline 2 | `POST /validation/run/{plan_id}`; `GET /validation/{plan_id}/findings?rule=&severity=` |
| Toggle a rule | `PUT /validation/rules` with `{"duplicates": {"enabled": false}}`; the next run changes |
| Contradictions and precedence | `GET /validation/contradictions`; `PUT /config/precedence`, then `POST /config/precedence/reapply` |
| Comparison (≥100 rows) | `POST /comparison/{plan_id}`; `GET /reports/comparison?format=csv` |
| Consistency | `POST /consistency/{plan_id}` (background job); `GET /consistency/{plan_id}` |
| Human review | `GET /review/queue`; `POST /review/{finding_id}/decision` (APPROVE, REJECT, EDIT, REGENERATE, COMMENT); `GET /audit/finding/{id}` |
| Progress and dashboards | `POST /progress/items/task/{id}`, `/progress/quiz/{id}/attempt`; `GET /dashboard/me`, `/dashboard/admin`, `/dashboard/roles` |
| Policy update | upload `POL-INFOSEC-001` v2 (v1 becomes OBSOLETE), `POST /impact/analyse/{v2_id}`, `GET /impact/{v2_id}/affected`, `GET /plans/{id}/outdated`, `POST /impact/{v2_id}/regenerate?dry_run=true` then `dry_run=false` |
| Reports and export | `GET /reports` lists the 8 report endpoints; each takes `?format=json\|csv\|xlsx\|pdf` |
| Search and filter | `GET /search/records?role=&department=&module=&policy=&status=&verification=&progress_min=&page=` |

`python -m scripts.bootstrap_demo` leaves InfoSec v2 out, so the policy-update flow can be shown live. Use `--with-v2` to include it.

## SRS coverage by step

| Step | Implementation |
|---|---|
| 3d Embeddings, search | `document_processing/embeddings.py`, `services/embedding_service.py`, `api/search.py`, HNSW index migration |
| 4 Matrix | `role_matrix/{extractor,role_mapper,prerequisites}.py`, `services/matrix_service.py`, `config/requirement_rules.yaml` |
| 5 Pipeline 1 | `genai_pipeline/`, `prompt_templates/` (versioned Jinja + manifest), `schemas/` (JSON Schema, mirrored in `src/schemas/generation.py`), `GenerationRun` |
| 6 Pipeline 2 | `python_validation/` (13 registered rules), `contradiction_checks/`, `ValidationResult` / `ValidationFinding` |
| 7 Comparison, review | `comparison_engine/{compare,status}.py`, `services/review_service.py`, append-only `audit_log` and `review_decisions` (ORM guard + DB trigger) |
| 8 Progress, dashboards | `progress/engine.py`, `services/progress_service.py` |
| 9 Policy updates | `impact/diff.py`, `services/impact_service.py`, `ImpactRecord` |
| 10 Reports, tests, deploy | `reports/export.py`, `services/report_service.py`, `tests/`, `Dockerfile`, `docker/entrypoint.sh` |

The demo corpus has 39 documents in PDF and DOCX, with 10 version pairs, 17 detected cross-document conflicts and
10 injection cases. It yields 327 requirements, 261 of them mandatory and 234 role-specific.

## Tests

```bash
docker compose up -d db
python -m pytest                    # 232 tests; the db-marked ones use a throwaway skillsprint_test database
python -m pytest tests/security -s  # writes docs/security_testing_report.md and prints the table
python -m pytest tests/test_isolation_guard.py   # Pipeline 2 imports nothing AI
```

`docs/ACCEPTANCE.md` maps every acceptance criterion in the brief to how to show it live and the test that proves it.

The GenAI API is mocked (the offline provider and scripted clients), so the suite needs no key and costs nothing.
The SRS test categories map to files as follows:

| Categories | File |
|---|---|
| functional, document upload, security, boundary | `tests/integration/test_10_*` |
| GenAI API, JSON, prompt injection | `tests/unit/test_genai_and_injection.py` |
| parsing, chunking, requirement extraction | `tests/unit/test_documents_and_matrix.py` |
| Python validation, source traceability, coverage, hallucination, contradiction, role relevance | `tests/unit/test_python_validation.py`, `tests/integration/test_20_*` |
| policy version, regeneration | `tests/unit/test_versions_progress_reports.py`, `tests/integration/test_40_*` |
| hidden-document readiness | `tests/integration/test_50_*` (an unseen DOCX and a brand-new role, end to end) |

## Performance

A full plan (about 35 modules, 300+ items) generates and validates in roughly 20 s with the offline provider on a
laptop. `tests/integration/test_20_*` asserts under 30 s. The fixes that keep it there:

- chunks are embedded at parse time, never at request time;
- retrieval scores every requirement against every active chunk in one NumPy product;
- the model is warmed in the FastAPI lifespan and baked into the Docker image;
- consistency testing runs as a background job, never inline.

With a live model the provider's latency is added, so use `generation.parameters.effort: low` for the timed demo.

## Deployment

The `Dockerfile` uses CPU-only PyTorch and bakes the embedding model into the image. `docker/entrypoint.sh` runs
`alembic upgrade head` and the seed on every start. Every secret (`SECRET_KEY`, `GENAI_API_KEY`, database
credentials, seed passwords) comes from environment variables, and no key is in the repository.

**Free tiers that sleep break two SRS requirements.** A dyno or container that spins down after inactivity
takes 30–60 s to wake, load PyTorch and warm the embedding model, so the first request fails the 30-second budget.
Periods of sleep also count as downtime against 99 % availability. This is handled as follows:

1. Deploy on an always-on instance: a paid Render or Railway service, or Fly.io with `min_machines_running = 1`,
   with 1 GB of RAM or more.
2. The container `HEALTHCHECK` and an external uptime monitor (for example UptimeRobot, every 5 minutes) hit
   `GET /health`. It checks the database and pgvector, and keeps any platform idle timer from firing.
3. Cold-start work is minimised: the model is inside the image, it is warmed at startup, and migrations are
   idempotent.

### Deploying to Railway

`railway.toml` builds the API from the `Dockerfile`, checks `GET /health` before routing traffic, and restarts on
failure. Railway sets `PORT`, which the entrypoint passes to uvicorn.

1. **Database.** Add a Postgres service that has pgvector, for example Railway's *pgvector* template (plain
   Postgres fails the first migration at `CREATE EXTENSION vector`).
2. **API.** Add a service from this GitHub repository. Railway picks up `railway.toml` from the repo root.
3. **Variables** on the API service:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (use your database service's name). The `postgresql://` form is converted to asyncpg automatically. |
   | `SECRET_KEY` | 32+ random characters: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `APP_ENV` | `production` |
   | `CORS_ORIGINS` | The frontend's URL, e.g. `https://skillsprint-web.up.railway.app` (comma separated for several) |
   | `SEED_ADMIN_PASSWORD`, `SEED_EVALUATOR_PASSWORD` | Your own values instead of the demo ones |
   | `GENAI_PROVIDER` | `offline`, or a provider plus its key (`GENAI_API_KEY`, `GEMINI_API_KEY`, ...) |
   | `BOOTSTRAP_DEMO` | `true` to load the Nexora Labs demo documents on start, otherwise leave unset |

4. **Uploads.** Attach a volume mounted at `/app/uploads`, or uploaded documents vanish on every redeploy.
5. **Domain.** Under *Networking*, generate a public domain. Then point the frontend at it with
   `VITE_API_BASE=https://<api-domain>` when building it, and put the frontend's URL in `CORS_ORIGINS`.

Give the service 1 GB of RAM or more: PyTorch and the embedding model load at start.

## Deviations from the brief (flagged, not silent)

- **Missing module restored**: `src/security/adversarial.py` was imported by `parse_service.py` but did not exist.
  I rebuilt it, with its patterns in `config/adversarial_patterns.yaml`.
- **Chunker**: an unnumbered paragraph under a numbered heading (an FAQ answer) now inherits that section id.
  Otherwise FAQ citations have no section to trace.
- **Audit log** was introduced in the Step 4 migration, because the Step 4 manual override must be recorded.
  Step 7 reuses it.
- **Offline provider**: added so the system and the tests run without a key. It is labelled in every run record.
- **Sampling parameters**: current Claude models fix sampling server-side, and the SDK no longer accepts
  `temperature`. Consistency runs therefore record temperature and seed, and pin what is controllable: the prompt
  version and the chunk set.
- **Precedence in the Matrix** (`POST /matrix/resolve-conflicts`): when two active documents disagree on the same
  obligation, or one restates the other (a handbook repeating a policy clause), the lower-ranked requirement is
  marked overridden. It is kept on record with the winner and the reason, and removed from the answer key.
  Without this, plans faithfully cover requirements that precedence says no longer apply. After a policy update,
  requirements that move in or out of the Matrix as a knock-on effect are regenerated too.
- **Resolved conflicts** (the plan follows the winning source) are reported at INFO and still counted in
  `contradiction_count`. Unresolved ones are ERROR. The level is set by `rules.contradictions.resolved_severity`.
- **Search paths**: semantic search is `GET /search`; the Step 10 record filter is `GET /search/records`.
- Pre-existing routes in `src/api/document.py` and `organization.py` still query directly. They were left as they
  were, and all new code follows api → services → repositories.
