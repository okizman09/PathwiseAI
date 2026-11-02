# Pathwise AI — Product Requirements Document

**Version:** 2.2  
**Date:** October 2, 2026  
**Status:** Beta build spec  
**Owner:** Product / Founder

---

## 1. Decisions (v2.2 delta)

| Area | Decision |
|---|---|
| Audience | Programmers and freelancers (building client sites, apps, proposals, docs, deployments). |
| Login | Google + email/password. **Login is required before an interview.** Tool directory is public. |
| Auth provider | **Supabase Auth** (Google, email verification, password reset). FastAPI only *verifies* the Supabase JWT. No hand-rolled signup/login/PBKDF2/JWT code. |
| Database | Postgres from day one (Supabase Postgres). SQLite only for local tests. Alembic migrations. |
| Quota | **2 workflow generations per user per day**, reset at 00:00 UTC (01:00 Lagos). Counted only when generation succeeds. Admins exempt. Quota lives in the DB, never in memory. |
| Hidden cost caps | Interview turns and step actions (regenerate / switch / finish) get their own generous caps, env-configurable. |
| Catalog | Admin supplies tool name + official URL + docs URL(s) + affiliate link. The LLM reads those pages and fills the card as draft, with sources recorded. Admin verifies. The LLM never invents tools or affiliate links. |
| Tool choice | **Rank, don’t filter.** Code shortlists by job match, then scores using constraints (budget, skill, stack). The LLM ranks the shortlist. |
| No tool match | The step shows “No verified tool yet. Come back later.” and the gap is logged so you know which tool to add next. |
| Explanations | Every step has short explanations (max two sentences each): why this step, why this tool, one thing to learn. |
| Persistence | Workflows and steps are stored server-side and tied to the account. /step uses server state, never client-sent state. No localStorage saved paths. |
| Money | open_url = affiliate_url or url, resolved **server-side** through a logged redirect (/go/{tool_id}). Show a small “affiliate link” note near Open tool. |
| Hosting | Frontend: Cloudflare. Backend: Render. DB and auth: Supabase. |

For full decisions, slice prompts, data model, and the master agent rules see [docs/PLAN.md](PLAN.md).

---

## 1a. What it is

Pathwise is a coach for programmers and freelancers. Someone types what they want to build. Pathwise learns the project, picks real verified tools, writes a step-by-step path, and gives a prompt written for each tool.

Creation happens **on the tool’s own site**. Pathwise does not generate the website, app, or design itself.

**Promise:** Tell us what you want to build. Get a clear path, verified tools, and prompts you can paste — and learn as you go.

---

## 2. Why v1 is being replaced

The current app is rejected because:

- Workflows are forced into 3 steps
- Follow-up questions use templates / mocks
- The directory shows hardcoded / mock tools
- Generation is split across server AI, browser key, and a local fake engine

v2 has **one path**: browser → API → cheap hosted LLM + verified catalog.

---

## 3. Who it is for

Beginners and intermediate creators who want to make sites, video, music, design, or content, but do not know which tool to use or how to prompt it.

---

## 4. What the user does

1. Types a goal.
2. Answers 0–5 LLM questions until there is a **product brief**.
3. Gets a plan (1–6 steps).
4. Opens the real tool, pastes the prompt, makes the thing.
5. Bad step: regenerate or switch tool.
6. Finished: short text note. Next prompt uses that note.

---

## 5. Product brief

Stop when you know: what, why, who, constraints, must-haves vs nice-to-haves.
Do not invent extra features. If the goal is enough, skip questions.

---

## 6. Tools catalog + Admin tab

**Source of truth:** backend database.

Admin adds tools in the **Admin Console / tab** (`/admin`).

1. Name + official **url** + **docs_url**
2. Optional **affiliate_url** (Impact, PartnerStack, or the tool’s referral link)
3. Server fetches docs_url only
4. LLM fills the card as `draft` — it must **not** invent affiliate_url
5. Admin edits and sets `verified`

Only verified tools appear in the directory and in workflows.

### Fields

name, url, docs_url, **affiliate_url** (optional), category, jobs, input_types, output_types, pricing, best_for, not_for, prompt_style, status (`draft` | `verified` | `hidden`), verified_at

### Open tool

`open_url = affiliate_url if set else url`

Same rule on directory cards and workflow “Open tool”. Users do not edit the affiliate string.

No scraper. No global rank. Dead official URL → hide.

---

## 7. Plan

1 step allowed. Typical 2–4. Cap 6. Never pad to 3.
No SEO/analytics unless asked. No invented tools. No match → `manual` or drop.

---

## 8. Pick a tool per step

Code filters by jobs + constraints + previous output type. Then LLM ranks the shortlist.
Primary + 1–2 alternatives. Switch rewrites that step only.

---

## 9. Prompts

Written for that tool’s `prompt_style`. Paste-ready. Copy / edit / regenerate.

---

## 10. Handoff

Off-platform. Text note only. Rewrite next prompt. No media upload.

---

## 11. Unhappy with a step

Regenerate, switch tool, or continue. Do not jump ahead.

---

## 12. Screens

1. Home
2. Interview
3. Workflow (Open tool = affiliate_url or url)
4. **Admin tab** — add name, url, docs_url, affiliate_url; review draft; verify; hide

Full user workspace (`/app`) and admin dashboard (`/admin`). Same API.

---

## 13. API

| Call | Notes |
|------|--------|
| POST /interview | question or ready + brief |
| POST /workflow | steps |
| POST /step | regenerate / switch_tool / finished |
| POST /admin/tools | name, docs_url, url, affiliate_url → draft |
| PATCH /admin/tools/{id} | including affiliate_url + status |
| GET /admin/tools | all statuses |
| GET /tools | verified only; includes affiliate_url |

---

## 14. Stack

React + FastAPI + SQLite/Postgres + Gemini Flash. No local SLM yet.

---

## 15. Money

MVP: affiliate_url on each tool. Open tool is the paid click.
Later: accounts + Pro subscription.

---

## 16. Out of scope

In-app generation, media-to-LLM, scraping, mocks, local SLM, native apps.

---

## 17. Build order

1. Catalog + affiliate_url + verify
2. Interview
3. Variable plan + prompts
4. Step retry / handoff
5. Thin UI
6. Full app workspace & admin console
7. Accounts / Stripe

---

## 18. Success

Copy rate, interview completion, variable step counts, verified-only tools, affiliate clicks when set.
