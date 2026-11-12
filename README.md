# Pathwise AI

> Turn a build idea into a clear step-by-step path: verified tools, paste-ready prompts, and live runs.

Pathwise AI interviews you about your project, locks a concrete product brief, picks verified tools from a curated catalog, and generates a sequenced plan. Prompt steps on supported text models can run live inside the app.

Example: *"I want a tool that turns my voice notes into structured orders."*

---

## Features

- **Guided interview.** 1–5 clarifying questions turn a rough goal into a concrete product brief (purpose, audience, must-haves, constraints, budget, skill level).
- **Sequenced plans.** 1–6 step creation paths: the right tool per step, paste-ready prompts or setup steps, expected outputs, and handoff notes that carry context forward.
- **Verified tool catalog.** Curated tools with pricing and free-tier notes, warning flags, and a Meta models directory with call snippets.
- **Live runs.** Prompt steps on runnable text models execute in-app, with saved outputs, copy/`.md` export, and daily quotas.
- **History.** Every creation path is saved, reopenable, renameable, and deletable.
- **Feedback that improves the product.** Per-step worked/partly/didn't signals, a landing-page feedback form with email notifications, and CSV exports from the admin console.

## Quickstart (local)

Prerequisites: Python 3.11+, Node.js 20 LTS or newer.

```bash
# Backend (http://localhost:8000)
cd backend
python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env             # then fill in MODEL_API_KEY and the Supabase values
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000

# Frontend (usually http://localhost:5173)
cd frontend
npm install
npm run dev
```

Deploying to production (Render + Cloudflare + Supabase) is covered in `docs/DEPLOY.md`.

## Environment variables

Backend (`backend/.env`, see `backend/.env.example`). Never commit real values.

| Key | Purpose |
|---|---|
| `MODEL_API_KEY` | Model API key (server-only; never in frontend code) |
| `META_BASE_URL` | `https://api.meta.ai/v1` |
| `META_MODEL` | `muse-spark-1.3` |
| `LLM_TIMEOUT_SECONDS` | Per-call model timeout (`90`) |
| `DATABASE_URL` | SQLite locally; Supabase Postgres URI in production |
| `CORS_ORIGINS` | Allowed frontend origins |
| `SUPABASE_URL` / `SUPABASE_JWT_SECRET` / `SUPABASE_JWT_AUDIENCE` | Auth + JWT verification |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only: account deletion, logo uploads |
| `WORKFLOWS_PER_DAY` / `INTERVIEW_TURNS_PER_DAY` / `STEP_ACTIONS_PER_DAY` / `RUN_STEPS_PER_DAY` | Daily quotas (`2` / `25` / `20` / `10`) |
| `RUN_MAX_PROMPT_CHARS` / `RUN_MAX_OUTPUT_TOKENS` / `RUN_TIMEOUT_SECONDS` | Live-run caps (`6000` / `8192` / `60`) |
| `RESEND_API_KEY` / `FEEDBACK_NOTIFY_TO` / `FEEDBACK_NOTIFY_FROM` | Email notification for landing-page feedback (Resend HTTP API; empty disables) |

Frontend (`frontend/.env`, see `frontend/.env.example`). `VITE_*` values ship in the client bundle and are public by design: `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.

## Tests

```bash
cd backend
python -m pytest          # offline suite (SQLite, mocked LLM)
python -m ruff check .

cd ../frontend
npx tsc --noEmit
npm run build
```

## Project structure

```text
backend/        # FastAPI + SQLAlchemy + Alembic; LLM client in app/services/llm.py
backend/scripts # meta_hello.py, smoke_plan.py, audit_tools.py, backfill/rewrite helpers
backend/data    # meta_cards.json (Meta cards), manus_card.json
frontend/       # TanStack Start app (routes: landing, workspace, directory, history, admin)
files/          # Reference pack: playbook, PRD, spec
docs/           # Deploy guide, catalog notes, PRD/spec copies
```

## Limitations

- Live Run is text-only: only verified `runnable` text models with a `model_id` can run. Image, voice, and transcription steps always paste out.
- The model API is paid with no free tier, so `free_only` budgets exclude live runs. The UI says so when a plan has zero runnable steps.
- Catalog pricing coverage is incomplete; unknown pricing is labeled, never guessed.
- Interview turns and generation take roughly 10–60 s per model call.
- First request after idle is slow (cold database connections); steady-state page loads are sub-second on warm connections.

## Roadmap

- Live Run for more models (image output, then audio/transcription).
- An agent loop with verification (run a step, check the result, retry or advance).
- A skills system (reusable prompt/artifact packs per domain).
- Wider catalog pricing coverage and automated rechecks.

## Owner

Pathwise AI is built and maintained by the owner — okizmanofficial@gmail.com.
