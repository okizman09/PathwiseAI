# Pathwise AI

> **For programmers and freelancers: turn your build idea into a clear step-by-step path with verified tools and paste-ready prompts.**

Pathwise AI interviews you about your project, locks down a concrete product brief, picks verified tools from a curated database, and generates tailored prompts for each stage — one prompt per tool, ready to paste.

---

## Architecture

```
Pathwise AI/
├── backend/                        # FastAPI · SQLAlchemy 2 · Alembic · Gemini
│   ├── app/
│   │   ├── main.py                 # App entry-point, middleware, router mounts
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic settings (production guard, JWKS, secrets)
│   │   │   ├── errors.py           # Sanitized error handling (ERR-xxx)
│   │   │   ├── rate_limit.py       # Persistent database-backed rate limiter
│   │   │   └── signing.py          # Cryptographically signed link tracking tokens
│   │   ├── db.py                   # SQLAlchemy engine, Base, session
│   │   ├── models/                 # SQLAlchemy ORM models (Tool, Workflow, RateLimitBucket, etc.)
│   │   ├── schemas/                # Pydantic schemas (public vs admin schemas)
│   │   ├── routers/                # Route handlers (/health, /go, /api/v1/...)
│   │   ├── api/
│   │   │   └── deps.py             # Dependencies (Supabase auth, email verification, beta allowlist)
│   │   ├── services/
│   │   │   ├── catalog.py          # Tool verification, catalog queries
│   │   │   ├── interview.py        # Interview turns, brief finalization
│   │   │   ├── plan.py             # Workflow generation, job planning
│   │   │   ├── prompts.py          # Tool-specific prompt engineering
│   │   │   └── research/           # Hardened tool research & doc scraping pipeline
│   │   └── scripts/
│   │       ├── check_connections.py# Non-interactive connection diagnostics
│   │       ├── make_admin.py       # CLI admin promotion tool
│   │       └── seed_candidates.py  # Idempotent tool catalog seeding (--research support)
│   ├── tests/                      # Comprehensive pytest test suite (47+ tests)
│   ├── requirements.txt            # Production dependencies
│   ├── requirements-dev.txt        # Dev/test: pytest, httpx, ruff, freezegun
│   └── .env.example                # Backend vars template (copy → backend/.env)
│
├── frontend/                       # TanStack Start · Vite · React 19 · TypeScript
│   ├── src/
│   │   ├── content/                # Markdown legal documents (privacy.md, terms.md)
│   │   ├── routes/
│   │   │   ├── index.tsx           # Public landing page
│   │   │   ├── login.tsx           # Sign in / Sign up (Supabase Auth)
│   │   │   ├── app.tsx             # Creator workspace (/app)
│   │   │   ├── app_.history.tsx    # Saved workflow paths (/app/history)
│   │   │   ├── tools.tsx           # Public tool directory (/tools)
│   │   │   ├── admin.tsx           # Admin catalog console (/admin)
│   │   │   ├── privacy.tsx         # Privacy policy (/privacy)
│   │   │   └── terms.tsx           # Terms of service (/terms)
│   │   ├── components/             # Reusable UI & layout components (AppHeader, MarkdownViewer)
│   │   └── lib/
│   │       ├── api.ts              # Typed backend API client (/api/v1 prefix, error types)
│   │       └── supabase.ts         # Supabase browser client
│   └── .env.example                # Frontend vars template — public VITE_* vars
│
└── docs/
    ├── PRD.md                      # Product requirements document
    ├── PLAN.md                     # Engineering slice plans
    └── DEPLOY.md                   # Production deployment guide
```

---

## Hosting & Deployment

| Layer | Service | Deployment Guide |
|---|---|---|
| Frontend | Cloudflare Pages / Workers | [docs/DEPLOY.md](docs/DEPLOY.md#step-5-cloudflare-frontend-deployment) |
| Backend | Render | [docs/DEPLOY.md](docs/DEPLOY.md#step-4-render-backend-deployment) (`render.yaml`) |
| Database + Auth | Supabase (Postgres + Auth) | [docs/DEPLOY.md](docs/DEPLOY.md#step-1-supabase-setup-database--auth) |

For complete step-by-step production deployment instructions, see **[docs/DEPLOY.md](docs/DEPLOY.md)**.

---

## Local Development

### Prerequisites

- **Python** 3.11+
- **Node.js** 20+
- **Gemini API key** — [Google AI Studio](https://aistudio.google.com/)

---

### 1. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Configure environment
cp .env.example .env
# Edit backend/.env — set GEMINI_API_KEY, SUPABASE_URL, etc.
```

Run database migrations:

```bash
alembic upgrade head
```

Start the development server:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

- API Root & Health: `http://localhost:8000/health`
- API v1 Base: `http://localhost:8000/api/v1`
- Swagger UI (development only): `http://localhost:8000/docs`

Run diagnostic connection checks:

```bash
python -m app.scripts.check_connections
```

---

### 2. Frontend

```bash
cd frontend

npm install

# Configure environment
cp .env.example .env
# Edit frontend/.env — set VITE_API_URL=http://localhost:8000
```

Start the development server:

```bash
npm run dev
```

Open `http://localhost:5173`.

---

## Routes

| Route | Description | Access |
|---|---|---|
| `/` | Public landing page | Public |
| `/tools` | Verified tool directory (server-routed links) | Public |
| `/privacy` | Privacy policy document | Public |
| `/terms` | Terms of service document | Public |
| `/login` | Sign in / Sign up / Forgot password | Public |
| `/app` | Creator workspace — interview → workflow path | Authenticated (Verified email) |
| `/app/history` | Saved workflow paths history | Authenticated |
| `/admin` | Tool catalog review & verification dashboard | Admin role only |

---

## Running Tests & Linting

```bash
cd backend
python -m pytest
python -m ruff check .
```

All 47+ backend tests run against an in-memory SQLite database and execute in ~8 seconds.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `ENVIRONMENT` | Yes | `development` or `production` |
| `DATABASE_URL` | Yes | SQLite (local) or Supabase Postgres URI |
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `GEMINI_MODEL` | No | Default `gemini-2.5-flash` |
| `SUPABASE_URL` | Yes | Supabase Project URL (`https://<ref>.supabase.co`) |
| `SUPABASE_JWT_SECRET` | No | Legacy secret (optional when using asymmetric JWKS via `SUPABASE_URL`) |
| `SUPABASE_JWT_AUDIENCE`| No | Default `authenticated` |
| `SUPABASE_SERVICE_ROLE_KEY` | No | **Server-only!** Enables server-side account deletion (`DELETE /api/v1/me`) |
| `APP_SIGNING_SECRET` | Yes | Secret used for signing link tracking tokens |
| `CORS_ORIGINS` | Yes | Allowed origins (e.g. `http://localhost:5173` or production Cloudflare URL) |
| `BETA_ALLOWLIST_ENABLED` | No | Default `false`. If `true`, restricts paths to allowlisted emails |
| `BETA_ALLOWED_EMAILS` | No | Comma-separated list of invited creator emails |
| `SENTRY_DSN` | No | Optional backend Sentry monitoring (sensitive data scrubbed) |
| `WORKFLOWS_PER_DAY` | No | Free tier workflow paths cap (default `2`) |
| `INTERVIEW_TURNS_PER_DAY` | No | Free tier interview turns cap (default `25`) |
| `STEP_ACTIONS_PER_DAY` | No | Free tier step actions cap (default `20`) |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | Yes | Backend URL, e.g. `http://localhost:8000` |
| `VITE_SUPABASE_URL` | Yes | Public Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Yes | Public Supabase anon key (safe in browser) |
| `VITE_FEEDBACK_URL` | No | Optional feedback or issues link shown in the app header |

---

## License

MIT License. Created for Pathwise AI.
