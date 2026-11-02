# Pathwise AI — Tool Catalog Architecture & Operations (Catalog v3)

This document defines the architecture, taxonomy, quality standards, and operating procedures for the Pathwise AI Tool Catalog.

---

## 1. Principles

1. **Zero Hallucinated Claims**: No pricing tier, limit, or capability claim is published without a verbatim quotation from an official domain.
2. **Taxonomy Discipline**: Tools belong to exactly one primary creator domain from a fixed 9-domain taxonomy. Capabilities use standard job slugs.
3. **No Dead Links**: Automated daily monitors verify reachability. Broken links are hidden immediately to protect creator trust.
4. **Honest Monetization**: Affiliate links are clearly marked with disclosure notices and never distort editorial rankings or pricing data.

---

## 2. Taxonomy Structure

The catalog organizes the creator software landscape into **9 primary domains**, defined in `backend/app/taxonomy/taxonomy.yaml` and exposed at `GET /taxonomy`:

| Domain Slug | Creator Domain | Example Tools |
| :--- | :--- | :--- |
| `software` | AI Coding & Engineering | Cursor, Claude Code, GitHub Copilot, Windsurf |
| `builders` | Visual & AI App Builders | Replit, Lovable, Bolt.new, v0, Framer |
| `design` | Graphic, UI & Visual Generation | Figma, Canva, Adobe Firefly, Midjourney, Ideogram |
| `video` | AI Video Generation & Editing | Runway, CapCut, Descript, HeyGen, Kling AI |
| `audio` | AI Music, Voice & Audio Tools | Suno, Udio, ElevenLabs, Audacity, Otter.ai |
| `writing` | AI Writing, Editing & LLMs | ChatGPT, Claude, Gemini, Grammarly |
| `research` | Knowledge Synthesis & Notes | Perplexity, NotebookLM, Notion, Obsidian |
| `deploy_backend` | Hosting, Database & Infrastructure | Supabase, Vercel, Cloudflare, Render, Netlify |
| `freelance_ops` | Operations, Payments & Booking | Stripe, Calendly, Loom |

Each domain defines approved **job slugs** (e.g., `write_code`, `generate_voiceover`, `edit_video`, `host_database`). Tools may only declare jobs that exist within the taxonomy.

---

## 3. Tool Status Levels & Lifecycle

A tool progresses through four strict lifecycle states:

```
[ tools.csv ] ──> ( DRAFT ) ──[ Card Importer ]──> ( RESEARCHED ) ──[ Admin Verification ]──> ( VERIFIED )
                                                                                                  │
                                                                       [ Link Dead / Archived ] ──▼
                                                                                               ( HIDDEN )
```

1. **`draft`**:
   - Initial entry created via CSV seeding (`python -m app.scripts.seed_candidates`) or manual creation in `/admin`.
   - Has basic identity (`name`, `url`, `domain`, `official_domains`), but no verified capabilities.
   - **Visibility**: Internal only; never shown on `/tools` or in planner recommendations.

2. **`researched`**:
   - Upgraded automatically when an imported card JSON is ingested via `CardImporterService`.
   - Populated with extracted pricing, claims, evidence quotes, and automated consistency flags (`review_flags`).
   - **Visibility**: Internal only; awaiting admin audit.

3. **`verified`**:
   - Has successfully passed all **8 Verification Conditions** in the admin review console.
   - Records `verified_at`, `verified_by`, and `pricing_checked_at`.
   - **Visibility**: Published live in the public catalog (`/tools`) and available for creator workflows. Public cards display the `"Verified <Mon YYYY>"` badge.

4. **`hidden`**:
   - Automatically set if daily health checks detect a dead primary link (`link_status = 'dead'`), or manually archived by an administrator.
   - **Visibility**: Removed from public browsing and planner shortlists until resolved.

---

## 4. What "Verified" Means: The 8 Verification Conditions

An administrator cannot verify a tool until the system confirms all 8 rules are satisfied:

1. **Domain**: Must match one of the 9 official taxonomy domains.
2. **Jobs**: Must declare at least one valid taxonomy job slug.
3. **Pricing Model**: Must be explicitly set (`free`, `freemium`, `free_trial`, `paid`, or `open_source`), never `unknown`.
4. **Free Tier Consistency**: If pricing model is `free`, `freemium`, or `free_trial`, `has_free_tier` must be set. If `has_free_tier` is `true`, `free_tier_summary` must be non-empty.
5. **Evidence Provenance**: Every claimed pricing attribute (`pricing_model`, `has_free_tier`, `starting_price_monthly_usd`, `credit_card_required`, `watermark_on_free`, `commercial_use_on_free`) must have a corresponding verbatim quote and source URL from an approved official domain.
6. **Copy Length Limits**:
   - `tagline`: Maximum 90 characters.
   - `free_tier_summary`: Maximum 140 characters.
   - `pros`: Exactly 3 distinct items.
   - `cons`: Exactly 3 distinct items.
7. **Link Reachability**: Primary URL must be reachable via HTTPS (`link_status == 'ok'`).
8. **Resolved Review Flags**: All `review_flags` (such as quote mismatches, off-domain claims, or audit notes) must be cleared or resolved.

---

## 5. Pathwise Picks (`is_pick`)

- The **Pathwise Pick** badge highlights best-in-class, battle-tested tools across specific jobs (e.g. Cursor for coding, Supabase for backend, ElevenLabs for voice).
- **Hard Restriction**: A tool can **only** be marked as a Pathwise Pick if its status is `verified`. Setting `is_pick = true` on a draft or unverified tool is rejected by the server.
- **Ranking**: Picks appear first in public directory views and receive priority weighting during workflow planning.

---

## 6. Freshness & The 30-Day Recheck Rule

Pricing in the AI creator space changes frequently. Pathwise enforces continuous freshness:

1. **Stale Filter (`GET /admin/tools/stale`)**:
   - Any verified tool whose `pricing_checked_at` is older than 30 days is classified as **stale**.
   - Admin console provides a one-click `Stale (>30d)` filter pill for auditing.
2. **Fresh JSON Diffing**:
   - When updating a tool, admins paste the latest research JSON into the **Recheck** drawer.
   - The system displays a field-by-field diff (Current vs. New) before applying.
   - Applying updates claims and resets `pricing_checked_at` to current time while **preserving existing affiliate URLs**.
3. **Automated Link Checker (`POST /admin/jobs/check-links`)**:
   - Scheduled via Render Cron (daily at `0 4 * * *`).
   - Automatically hides tools whose official URLs are broken.

---

## 7. Research & Ingestion Workflow

To add or update tools in the catalog:

### Step 1: Run Research via Perplexity
Run research using the standard extraction prompt against official pricing and documentation pages:
- Target official pricing pages (`/pricing`) and documentation.
- Collect exact quotes and URLs for all claims.

### Step 2: Audit Card JSON
Ensure the extracted JSON conforms to the Catalog v3 specification:
- Official domains list populated.
- Exactly 3 pros and 3 cons.
- Valid taxonomy job slugs.

### Step 3: Run Importer
Ingest the cards into the database:
```bash
python -m app.scripts.import_cards --expect tools.csv data/cards.json
```
The importer automatically:
- Checks source URLs against official domains.
- Performs normalized quote matching against live pages.
- Flags mismatches as `review_flags`.
- Upgrades matching drafts to `researched`.

### Step 4: Admin Audit & Verification
1. Open `/admin`.
2. Inspect green (verified) and red (mismatch) evidence badges.
3. Resolve review flags.
4. Click **Verify & Publish**.

---

## 8. Creator Usage Signals & Feedback (Slice C7)

To continuously measure how verified tools perform in real creator workflows:

1. **Step Completion Feedback**:
   - When a creator marks a step finished, the app asks: *"Did this step work?"*
   - Options: **Worked** (1.0), **Partly** (0.5), or **Didn't** (0.0), with an optional note.
   - Stored in the `step_feedback` table.
2. **Public Threshold Rule**:
   - The badge *"Used in N workflows"* appears on public tool cards only once a tool reaches **at least 10 feedback entries**.
   - Tools below this threshold show no count badge.
3. **Creator Privacy**:
   - Individual user notes and detailed ratings are strictly private to administrators.
   - Public API endpoints and cards never expose feedback notes.
4. **Admin Usage Metrics (`GET /admin/tools/metrics`)**:
   - The admin console displays aggregate metrics per tool: total feedbacks, success rate percentage, worked/partly/didn't breakdown, and badge eligibility.

