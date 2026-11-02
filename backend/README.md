# Pathwise AI — Backend API

FastAPI backend for Pathwise AI — an intelligent coach that learns a user's creation goal, selects real verified tools from a database catalog, produces a tailored step-by-step path (1–6 steps), and crafts custom paste-ready prompts for each tool's specific prompt style.

---

## 🛠️ Stack & Architecture

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL (Production Supabase) / SQLite (Local / Tests), managed via SQLAlchemy 2 + Alembic
- **LLM Engine**: Meta Muse (`muse-spark-1.3` via the Meta Model API and OpenAI SDK)
- **Authentication**: Supabase JWT (ES256 / RS256 JWKS or HS256 secret) with server-enforced verified email checks
- **Rate Limiting**: Database-backed persistent rate limiter surviving restarts
- **Security**: Cryptographically signed link-tracking tokens (`/go/{id}`), hardened SSRF fetcher with streaming size caps

---

## 🚀 Setup & Installation

### 1. Create Virtual Environment
```bash
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Set at minimum:
```env
ENVIRONMENT=development
MODEL_API_KEY=your_model_api_key_here
META_MODEL=muse-spark-1.3
DATABASE_URL=sqlite:///./pathwise.db
SUPABASE_URL=https://<your-project-ref>.supabase.co
APP_SIGNING_SECRET=your-random-32-char-secret-for-signing
```

### 4. Run Migrations & Start Server
```bash
alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```

- Health Endpoint: [http://localhost:8000/health](http://localhost:8000/health)
- API v1 Root: [http://localhost:8000/api/v1](http://localhost:8000/api/v1)
- Swagger Docs (dev mode only): [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📡 API Endpoints (Prefix: `/api/v1`)

All application routes are mounted under `/api/v1`, with only `/health` and `/go/{tool_id}` at the root:

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/health` | API & database connectivity check | Public |
| `GET` | `/go/{tool_id}` | Signed click tracking & safe redirection | Public / Tracked |
| `GET` | `/api/v1/tools` | Directory of verified tools (server-routed links) | Public |
| `POST` | `/api/v1/interview` | Creator goal interview turns | Bearer JWT (Verified) |
| `POST` | `/api/v1/workflows` | Generate a 1–6 step creation path from brief | Bearer JWT (Verified) |
| `GET` | `/api/v1/workflows` | List saved creation paths | Bearer JWT |
| `GET` | `/api/v1/workflows/{id}` | Retrieve specific creation path | Bearer JWT |
| `POST` | `/api/v1/workflows/{id}/steps/{step_id}/finish` | Mark step completed with handoff note | Bearer JWT (Verified) |
| `POST` | `/api/v1/workflows/{id}/steps/{step_id}/switch-tool` | Switch primary tool to associated alternative | Bearer JWT (Verified) |
| `POST` | `/api/v1/workflows/{id}/steps/{step_id}/recheck` | Recheck primary tool recommendation | Bearer JWT (Verified) |
| `POST` | `/api/v1/workflows/{id}/steps/{step_id}/open-link` | Generate cryptographically signed `/go/{id}` link | Bearer JWT |
| `GET` | `/api/v1/quota` | Check current daily quota counters | Bearer JWT |
| `DELETE`| `/api/v1/me` | Delete account and all user data permanently | Bearer JWT |
| `GET` | `/api/v1/admin/tools` | Manage catalog (filter by draft/verified/hidden) | Admin role |
| `POST` | `/api/v1/admin/tools` | Add candidate tool (triggers Meta doc research) | Admin role |
| `PATCH`| `/api/v1/admin/tools/{id}`| Update tool fields or verify candidate | Admin role |

---

## 🧪 Testing & Diagnostics

```bash
# Run connection diagnostics
python -m app.scripts.check_connections

# Run unit and integration tests
python -m pytest

# Run linter
python -m ruff check .
```
