# Pathwise AI

> Turn a build idea into a clear step-by-step path: verified tools, paste-ready prompts, and live runs — all powered by Meta's models.

Pathwise AI interviews you about your project, locks a concrete product brief, picks verified tools from a curated catalog, and generates a sequenced plan. Prompt steps on Meta's text models can run live inside the app.

Demo goal: *"I want a tool that turns my voice notes into structured orders."*

---

## What is new for the hackathon

Built during the event window (see `NEW_WORK.md` for the per-task log):

- **Meta-only provider.** All LLM calls (interview, planner, step actions, live runs) go through the Meta Model API at `https://api.meta.ai/v1` on `muse-spark-1.3`, using strict `json_schema` structured output. The previous provider code is deleted.
- **Meta directory.** 9 verified Meta cards (models, tools, and platforms) with live-checked facts, call snippets, and a Meta-only browse view plus a Models view.
- **Meta-aware planner.** 1–6 step plans that prefer Meta models for matching jobs, ask for the product name, skip redundant hosting/database steps when the builder covers them natively, and emit setup steps (not prompts) for deploy/database/auth jobs.
- **Live Run (stretch, shipped).** Prompt steps on runnable Meta text models execute in-app with persisted runs, copy/`.md` export, and a 10/day quota.
- **Hardening.** Row-Level Security on all tables, per-request performance fixes (auth write throttle, batched hydration, cached directory), and low-latency reasoning on the creation path.

## Quickstart (local)

Prerequisites: Python 3.11+, Node.js 20 LTS or newer.

```bash
# Backend (http://localhost:8000)
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows; use source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
copy .env.example .env        # then fill in MODEL_API_KEY and the Supabase values
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000

# Frontend (Vite default port, usually http://localhost:5173)
cd frontend
npm install
npm run dev
```

Deploying to production (Render + Cloudflare + Supabase) is covered in `docs/DEPLOY.md`.

## Environment variables

Backend (`backend/.env`, see `backend/.env.example`). Never commit real values.

| Key | Purpose |
|---|---|
| `MODEL_API_KEY` | Meta Model API key (server-only; never in frontend code) |
| `META_BASE_URL` | `https://api.meta.ai/v1` |
| `META_MODEL` | `muse-spark-1.3` |
| `LLM_TIMEOUT_SECONDS` | Per-call model timeout (`90`) |
| `DATABASE_URL` | SQLite locally; Supabase Postgres URI in production |
| `CORS_ORIGINS` | Allowed frontend origins |
| `SUPABASE_URL` / `SUPABASE_JWT_SECRET` / `SUPABASE_JWT_AUDIENCE` | Auth + JWT verification |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only: account deletion, logo uploads |
| `WORKFLOWS_PER_DAY` / `INTERVIEW_TURNS_PER_DAY` / `STEP_ACTIONS_PER_DAY` / `RUN_STEPS_PER_DAY` | Daily quotas (`2` / `25` / `20` / `10`) |
| `RUN_MAX_PROMPT_CHARS` / `RUN_MAX_OUTPUT_TOKENS` / `RUN_TIMEOUT_SECONDS` | Live-run caps (`6000` / `8192` / `60`) |

Frontend (`frontend/.env`, see `frontend/.env.example`). `VITE_*` values ship in the client bundle and are public by design: `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.

## Tests

```bash
cd backend
python -m pytest          # 185 tests (SQLite, mocked LLM)
python -m ruff check .

cd ../frontend
npx tsc --noEmit
npm run build
```

Live checks that need a key (run yourself, never commit output with secrets):

```bash
cd backend
$env:MODEL_API_KEY="<your-key>"   # export MODEL_API_KEY=<your-key> on macOS/Linux
python scripts/meta_hello.py      # T1 gate: models, text, json_schema, streaming
python scripts/smoke_plan.py      # 8-goal end-to-end smoke (saves under user 'smoke-t7')
python scripts/audit_tools.py     # catalog issue report (read-only)
```

## Project structure

```text
backend/        # FastAPI + SQLAlchemy + Alembic; Meta client in app/services/llm.py
backend/scripts # meta_hello.py, smoke_plan.py, audit_tools.py, backfill/rewrite helpers
backend/data    # meta_cards.json (9 Meta cards), manus_card.json
frontend/       # TanStack Start app (routes: landing, workspace, directory, history, admin)
files/          # Hackathon pack: playbook, PRD, spec
docs/           # Deploy guide, catalog notes, PRD/spec copies
mockups/        # Landing/app redesign mockups (reference only)
NEW_WORK.md     # Per-task build log for the event window
```

## Honest limitations

- Live Run is text-only: only verified `runnable` text models with a `model_id` (Muse Spark, Muse Wonder) can run. Image, voice, and transcription steps always paste out.
- Meta API models are paid with no free tier, so `free_only` budgets exclude them — and therefore exclude live runs. The UI says so when a plan has zero runnable steps.
- Catalog pricing coverage is incomplete (~100 tools still unchecked); unknown pricing is labeled, never guessed.
- Reasoning-model latency: interview turns and generation take roughly 10–60 s per model call even after the low-effort tuning.
- First request after idle is slow (cold database connections measured at several seconds); steady-state page loads are sub-second on warm connections.
- RLS is enabled with zero permissive policies: all data flows through the backend; nothing reads tables directly from the client.

## Roadmap

- Live Run for more models (image output, then audio/transcription).
- An agent loop with verification (run a step, check the result, retry or advance).
- A skills system (reusable prompt/artifact packs per domain).
- Wider catalog pricing coverage and automated rechecks.
