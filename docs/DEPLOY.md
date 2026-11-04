# Pathwise AI — Production Deployment Guide

This guide provides step-by-step instructions to deploy Pathwise AI from a clean clone to production.

---

## Architecture Overview

- **Frontend**: [Cloudflare Pages / Workers](https://pages.cloudflare.com/) (TanStack Start, Nitro `cloudflare-module` preset).
- **Backend API**: [Render](https://render.com/) Web Service (FastAPI, Python 3.11+, Uvicorn).
- **Database**: [Supabase Postgres](https://supabase.com/) with Alembic migrations.
- **Authentication**: [Supabase Auth](https://supabase.com/docs/guides/auth) (Google OAuth 2.0 & Email/Password with verification).
- **LLM**: [Meta Model API](https://dev.meta.ai/) (`muse-spark-1.3`) via an OpenAI-compatible client.

---

## Step 1: Supabase Setup (Database & Auth)

### 1.1 Create Supabase Project
1. Go to [database.new](https://database.new) and create a new project.
2. Note your database password, project reference, and region.

### 1.2 Copy API Keys and Database URL
In the Supabase Dashboard:
1. **API Keys**: Go to **Project Settings** → **API**:
   - `Project URL` → This is `SUPABASE_URL` and `VITE_SUPABASE_URL`.
   - `anon / public` key → This is `VITE_SUPABASE_ANON_KEY`.
   - `JWT Settings` → **JWT Secret** → This is `SUPABASE_JWT_SECRET`.
2. **Database Connection String**: Go to **Project Settings** → **Database**:
   - Under **Connection string**, select **URI** and choose **Session** or **Transaction** pooler (port `5432` or `6543`).
   - Format: `postgresql://postgres.<project-ref>:[YOUR-PASSWORD]@aws-1-[region].pooler.supabase.com:5432/postgres`
   - This is `DATABASE_URL`.

### 1.3 Configure Supabase Authentication
1. Go to **Authentication** → **URL Configuration**:
   - **Site URL**: Enter your production frontend URL (e.g. `https://pathwise-ai.pages.dev`).
   - **Redirect URLs**: Add:
     - `http://localhost:5173/auth/callback`
     - `http://localhost:8080/auth/callback`
     - `http://localhost:8081/auth/callback`
     - `https://<your-cloudflare-subdomain>.pages.dev/auth/callback`
     - `https://<your-custom-domain>/auth/callback` (if using a custom domain)
2. Go to **Authentication** → **Providers** → **Email**:
   - Ensure **Enable Email provider** is **ON**.
   - Ensure **Confirm email** is **ON**.
3. Under **Authentication** → **Email Templates**:
   - Verify the Confirm Signup template redirect points to your frontend `/auth/callback`.

---

## Step 2: Google Cloud OAuth 2.0 Setup

To enable "Continue with Google" sign-in:

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Select your project and navigate to **APIs & Services** → **OAuth consent screen**:
   - User Type: **External**.
   - App Name: `Pathwise AI`.
   - User support email & Developer contact info: your email.
   - Authorized domains: Add `supabase.co`.
3. Navigate to **APIs & Services** → **Credentials**:
   - Click **Create Credentials** → **OAuth client ID**.
   - Application type: **Web application**.
   - Name: `Pathwise AI Web Client`.
   - **Authorized JavaScript origins**:
     - `https://<your-supabase-project-ref>.supabase.co`
     - `https://<your-cloudflare-subdomain>.pages.dev` (optional)
   - **Authorized redirect URIs**:
     - `https://<your-supabase-project-ref>.supabase.co/auth/v1/callback`
4. Copy the generated **Client ID** and **Client Secret**.
5. Back in **Supabase Dashboard** → **Authentication** → **Providers** → **Google**:
   - Toggle **Enable Google provider** to **ON**.
   - Paste **Client ID** and **Client Secret**.
   - Click **Save**.

---

## Step 3: Meta Model API Key

1. Go to [dev.meta.ai](https://dev.meta.ai/).
2. Create an API key and claim credits (card on file).
3. This is `MODEL_API_KEY` (server-only; never in frontend code or the repo).
4. (Recommended) Set budget and rate alerts in the Meta dashboard.

---

## Step 4: Render Backend Deployment

The repository includes a ready-to-use `render.yaml` Blueprint definition at the root.

### Option A: Deploy with Render Blueprint (Recommended)
1. Go to [dashboard.render.com](https://dashboard.render.com/) and click **New +** → **Blueprint**.
2. Connect your GitHub repository.
3. Render will read `render.yaml` and configure:
   - **Service Name**: `pathwise-backend`
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Pre-deploy Command**: `alembic upgrade head`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-proxy-headers`
   - **Health Check**: `/health`
4. Fill in the required environment variables prompted by the dashboard (see list below).
5. Click **Apply**.

### Option B: Manual Web Service Creation
1. Click **New +** → **Web Service**.
2. Connect your repo and set:
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Pre-Deploy Command**: `alembic upgrade head`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-proxy-headers`
   - **Health Check Path**: `/health`
3. Under **Environment Variables**, add the production values:

| Key | Value / Source |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | Supabase Postgres URI (`postgresql://...`) |
| `MODEL_API_KEY` | Your Meta Model API key (server-only) |
| `META_MODEL` | `muse-spark-1.3` |
| `META_BASE_URL` | `https://api.meta.ai/v1` |
| `RUN_STEPS_PER_DAY` | `10` |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `SUPABASE_JWT_SECRET` | Supabase JWT Secret (optional if `SUPABASE_URL` is configured for JWKS asymmetric validation) |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase `service_role` secret (used on backend for account deletion and logo upload to `tool-assets` bucket) |
| `SUPABASE_STORAGE_BUCKET` | `tool-assets` (Name of the public storage bucket for logos and preview images, default: `tool-assets`) |
| `APP_SIGNING_SECRET` | High-entropy random secret (>= 32 chars) for signing click tracking tokens |
| `CORS_ORIGINS` | Your Cloudflare frontend domain only, e.g. `https://pathwise-ai.pages.dev` |
| `TRUSTED_PROXY_COUNT` | `1` on Render (number of reverse proxies that append to `X-Forwarded-For`; the app reads the client IP from the END of that header so clients cannot fake it). Use `0` to ignore the header. |
| `CRON_SECRET` | Random secret for the link-check cron endpoint |
| `SENTRY_DSN` | Optional Sentry DSN (leave empty to disable) |
| `BETA_ALLOWLIST_ENABLED` | `false` (set `true` to enable private invite-only beta mode) |
| `BETA_ALLOWED_EMAILS` | Comma-separated list of permitted emails when beta mode is enabled |
| `SENTRY_DSN` | (Optional) Backend Sentry DSN for error monitoring with automatic payload scrubbing |
| `WORKFLOWS_PER_DAY` | `2` |
| `INTERVIEW_TURNS_PER_DAY` | `25` |
| `STEP_ACTIONS_PER_DAY` | `20` |

> ⚠️ **CRITICAL SECURITY WARNING — SERVICE-ROLE KEY**:
> `SUPABASE_SERVICE_ROLE_KEY` has full administrative bypass access to your Supabase project.
> - **NEVER** expose this key in `frontend/.env`, git repositories, client-side code, or public documentation.
> - It must **ONLY** be configured as a secret environment variable on your backend Render service to allow `DELETE /api/v1/me` to clean up Supabase auth records and server-side logo uploads to the `tool-assets` storage bucket.
> - In production (`ENVIRONMENT=production`), if `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_URL` is missing, storage upload operations raise a clear `RuntimeError`.

> **API Route Prefix**: All application endpoints are mounted strictly under `/api/v1` (e.g. `/api/v1/workflows`, `/api/v1/interview`, `/api/v1/tools`), with only `/health` and `/go/{tool_id}` mounted at the root.

4. Click **Deploy Web Service**.
5. Note your Render URL (e.g. `https://pathwise-backend.onrender.com`).

---

## Step 5: Cloudflare Frontend Deployment

The frontend uses TanStack Start, compiled for Cloudflare Workers via Nitro (`cloudflare-module` preset).

### Live Production Deployment
- **Frontend URL**: `https://pathwise-ai.okizmanofficial.workers.dev`
- **Backend URL**: `https://pathwiseai-gxo7.onrender.com`

### Cloudflare Workers Builds (Git Integration)
1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) → **Compute (Workers & Pages)** → Select worker `pathwise-ai`.
2. Under **Settings** → **Builds**:
   - **Root directory**: `frontend`
   - **Build command**: `npm run build`
   - **Deploy command**: `npx wrangler deploy`
3. [`wrangler.json`](file:///frontend/wrangler.json) automatically hooks into `npm run build` via `"build": { "command": "npm run build" }`.
4. Environment variables & secrets are configured in `wrangler.json` (or under **Variables and Secrets**):
   - `VITE_API_URL`: `https://pathwiseai-gxo7.onrender.com`
   - `VITE_SUPABASE_URL`: `https://igpzvyetvyqxsfftmjzr.supabase.co`
   - `VITE_SUPABASE_ANON_KEY`: `sb_publishable_G2qBkrdjIwhm5w0NydgvYw_GcvD5i5L`

---

## Step 6: Database Backup and Restore (PostgreSQL)

### 6.1 Automated Supabase Backups
- Supabase automatically schedules daily physical and WAL backups on Pro tier projects.
- Point-in-time recovery (PITR) is accessible directly under **Project Settings** → **Database** → **Backups**.

### 6.2 Manual Logical Backup (pg_dump)
To export a clean snapshot of your production data before making schema changes:
```bash
# Export schema and data into a compressed dump
pg_dump --clean --if-exists --no-owner --no-privileges \
  -d "postgresql://postgres.<project-ref>:[PASSWORD]@aws-1-[region].pooler.supabase.com:5432/postgres" \
  -F c -f pathwise_backup_$(date +%Y%m%d_%H%M%S).dump
```

### 6.3 Restoring from Backup (pg_restore / psql)
To restore a snapshot into a staging or recovery database:
```bash
# Restore custom-format dump file
pg_restore --clean --if-exists --no-owner --no-privileges \
  -d "postgresql://postgres.<project-ref>:[PASSWORD]@aws-1-[region].pooler.supabase.com:5432/postgres" \
  pathwise_backup_YYYYMMDD_HHMMSS.dump
```

---

## Step 7: Supabase Storage Bucket Setup (Tool Logos & Assets)

To store tool logos, preview images, and visual badges:
1. In the Supabase Dashboard, go to **Storage** → **Buckets**.
2. Click **New bucket**:
   - **Name**: `tool-assets` (The bucket must exist and be named `tool-assets`).
   - **Public bucket**: Toggle **ON** (The bucket MUST be public so logos and wide `og:image` previews can be loaded by web browsers and rendered in `<img />` tags).
   - **Allowed MIME types**: `image/png, image/jpeg, image/webp, image/svg+xml, image/x-icon`
   - **Max file size**: `1MB`
3. Click **Save bucket**.
4. In **Storage** → **Policies**, verify public read access:
   - Public buckets automatically allow `SELECT` / read operations to `anon` and unauthenticated callers.
5. **Required Environment Variables**:
   - `SUPABASE_URL`: `https://<project-ref>.supabase.co` (Used to build public asset URLs).
   - `SUPABASE_SERVICE_ROLE_KEY`: Supabase `service_role` secret (Used by the backend to authenticate write/upload operations).
   - `SUPABASE_STORAGE_BUCKET`: `tool-assets` (Configures bucket name; defaults to `tool-assets`).

---

## Step 8: Render Cron Job — Catalog Link Checker & Freshness

To keep the tool catalog fresh and automatically hide dead links:

1. In your Render Dashboard, add an environment variable to the backend Web Service:
   - `CRON_SECRET`: Generate a secure random token (e.g., `openssl rand -hex 24`).
2. Create a new **Cron Job** on Render:
   - **Name**: `pathwise-check-links`
   - **Schedule**: `0 4 * * *` (Daily at 04:00 UTC)
   - **Command**:
     ```bash
     curl -X POST https://your-backend.onrender.com/admin/jobs/check-links \
       -H "X-Cron-Secret: $CRON_SECRET"
     ```
3. What it does:
   - Checks primary URLs for all verified tools using SSRF-safe reachable checks.
   - If a link is dead, updates `link_status = 'dead'` and automatically sets `status = 'hidden'` to remove it from the public directory until resolved.
   - Updates `link_checked_at` timestamp.

---

## Step 9: First-Run Checklist (Catalog v3 Setup)

When deploying Pathwise AI from a clean setup, follow this 6-step checklist in order:

### 1. Migrate Database Schema
Execute Alembic migrations to apply all schema tables and Catalog v3 columns:
```bash
# In the Render Shell or deployment pipeline:
alembic upgrade head
```
Verifies creation of `tools`, `profiles`, `workflows`, `workflow_steps`, `step_feedback`, `usage_daily`, `events`, and `rate_limit_buckets`.

### 2. Seed Candidate Tools from tools.csv
Seed wave 1 candidates into the catalog as `draft` entries:
```bash
# In the Render Shell:
python -m app.scripts.seed_candidates
```
Populates all 44 tools with official URLs and taxonomy domains in `draft` status.

### 3. Import Researched Cards with Evidence
Ingest the researched card JSON files:
```bash
# In the Render Shell:
python -m app.scripts.import_cards --expect tools.csv cards.json
```
Upgrades matching draft tools to `researched`, validates pricing quotes against official domains, attaches evidence quotes, and flags discrepancies.

### 4. Create and Promote Administrator
1. Sign up on your live site using your designated admin email.
2. Confirm your email via the confirmation link sent to your inbox.
3. Promote the user record to `admin`:
   ```bash
   python -m app.scripts.make_admin your-admin@example.com
   ```

### 5. Review Claims & Verify in Admin Console
1. Log in to the application and navigate to `/admin`.
2. Inspect imported cards:
   - Review critical pricing claims next to verbatim evidence quotes.
   - Address and clear any `review_flags`.
   - Verify prompt engineering styles and input/output capabilities.
3. Click **Verify & Publish** once all 8 validation rules pass.

### 6. Mark Pathwise Picks
On verified tools that represent best-in-class workflows for creators (e.g. Cursor, Supabase, ElevenLabs), toggle **Pathwise Pick** (`is_pick`). Verified picks are highlighted with gold badges and prioritized in the public directory and planner recommendations.

### Check the client IP setting after the first deploy
Rate limits use the client IP. After deploying, open `/go/1` from two different networks (for example Wi-Fi and mobile data)
and look at the request logs: each network should log its own public IP. If both show the same address, or an address that
belongs to a proxy, set `TRUSTED_PROXY_COUNT` to `2` (or `0`) and redeploy.
