# Pathwise AI: Catalog v3 build instructions (for Antigravity)

This file is the single source of truth for the Catalog v3 work. Attach it to every Antigravity session.
Antigravity only writes code. Product decisions are made here; if something is unclear, ask before building.

---

## 0. Working rules (apply to every slice)

```text
You are the implementation engineer for Pathwise AI. You write code only.
- Work one slice at a time. After each slice output: (1) files created/changed, (2) how to run,
  (3) how I verify, (4) anything you were unsure about. Then stop and wait for "approved".
- If I write "change X", fix only X and stop again.
- No mock data and no fake LLM fallbacks. If a provider fails, return a clear error.
- Never hardcode secrets. Required secrets fail startup in production when missing.
- Enforce authorization on the SERVER. Frontend guards are UX only.
- Never trust client-supplied ids, urls, or workflow/step state.
- Validate all LLM or imported data with Pydantic. Treat fetched pages and imported JSON as untrusted.
- Every slice adds tests. External services (Gemini, Supabase) are mocked. Tests must not need the network
  or real DNS (mock socket/DNS resolution and HTTP).
- Do not add dependencies without listing them in the summary.
- Before using any external API (Supabase Storage, etc.), read its CURRENT docs. Do not code from memory.
```

## 1. Decisions

- Audience: anyone who wants to create with AI. Nine domains (section 2).
- Launch catalog: about 44 tools (wave 1, section 6), growing to about 100. Non-AI utilities (hosting, Canva, Audacity) are allowed.
- Research happens OUTSIDE the app (Perplexity app prompts). Results are imported as JSON and re-validated in code. No Perplexity API key is needed. Keep `ResearchProvider` as an interface so an API provider can be added later.
- No "Tested" badge. Two honest signals: **Verified** (facts checked against official sources, with a date) and, later, **Used by N people** (C7).
- Budget is the one hard filter: if the user says "free only", tools with no free tier are excluded. Everything else is ranking.
- Every tool has short explanations: tagline, summary, how it helps, pros, cons.
- Status levels: `draft` -> `researched` -> `verified` (and `hidden`).
- Product-level facts: `has_free_tier` and `pricing_model` describe the specific product on the card, not the vendor's other products (for example, Claude Code is paid only even though Claude chat has a free plan).

## 2. Taxonomy (controlled vocabulary)

Create `backend/app/taxonomy/taxonomy.yaml` with exactly these domains and job slugs. Add display labels (for example `write_code` -> "Write code").

```yaml
software:        [plan_app, write_code, debug_code, review_code, write_tests, write_docs, manage_code]
builders:        [build_website, build_web_app, build_mobile_app, build_landing_page, automate_workflow]
design:          [design_ui, generate_image, edit_image, design_brand, make_social_graphics, make_presentation]
video:           [write_script, storyboard_video, generate_video_clips, edit_video, add_captions, make_avatar_video, repurpose_clips]
audio:           [generate_music, generate_voiceover, transcribe_audio, edit_audio, record_podcast, separate_stems]
writing:         [draft_content, edit_proofread, optimize_seo, plan_content_calendar, schedule_social_posts, write_email_copy]
research:        [research_topic, summarize_documents, take_notes, organize_knowledge, analyze_data, manage_projects]
deploy_backend:  [host_frontend, host_backend, set_up_database, set_up_auth, monitor_errors, set_up_analytics]
freelance_ops:   [write_proposal, send_invoice, collect_payments, schedule_meetings, record_walkthroughs, find_clients]
```

## 3. Card JSON (what the importer accepts)

One object per tool. Keys and rules:

| Key | Type / allowed values | Limits |
|---|---|---|
| name | string | required |
| domain | one of the nine domain slugs | required |
| official_url, pricing_url | https URLs | pricing_url may be null |
| pricing_model | free, freemium, free_trial, paid, open_source, unknown | consistency rules in C2 |
| has_free_tier | true / false / null | permanent free plan for THIS product only |
| free_tier_summary | string or null | max 140 chars |
| free_tier_limits | string or null | one short sentence |
| starting_price_monthly_usd | number or null | cheapest paid individual plan billed monthly; no ranges |
| pricing_notes | string or null | annual pricing, credits, team plans |
| credit_card_required, watermark_on_free, commercial_use_on_free | true / false / null | null if not stated officially |
| platforms | list of web, desktop, mobile, cli, api, extension | |
| skill_level | beginner, intermediate, advanced, all | |
| jobs | list of taxonomy slugs for the card's domain (cross-domain slugs allowed) | 1 to 5 |
| tagline | string | max 90 chars |
| summary | string | 2 to 3 sentences |
| how_it_helps | string | 1 to 2 sentences |
| pros, cons | list of strings | exactly 3 each |
| prompt_style | {technique, format, rules[], example} or null | rules may be a string or list; normalize to list |
| input_types, output_types | list of short strings | |
| best_for, not_for | string | one sentence each |
| evidence | map of field -> {source_url, quote} or null | quote max 20 words; fields: pricing_model, has_free_tier, starting_price_monthly_usd, credit_card_required, watermark_on_free, commercial_use_on_free |
| unknowns | list of strings | strings starting with "check:" are review notes |
| checked_on | YYYY-MM-DD | |

---

## 4. Slices

### C0: Housekeeping

```text
C0: Housekeeping.
1. Make the tests that touch the fetcher, SSRF checks, seed script and affiliate URL validation
   independent of the network: mock DNS resolution (socket.getaddrinfo) and HTTP responses.
   `python -m pytest` must pass offline.
2. Add `.tanstack/` and `*.db` to .gitignore if missing.
3. Keep admin routes' specific error messages, but make sure no non-admin route returns raw
   exception text.
Done when: the full backend test suite passes with the network disabled.
```

### C1: Taxonomy and schema

```text
C1: Taxonomy and structured catalog schema.

1. Add backend/app/taxonomy/taxonomy.yaml (section 2), a loader with validation, and a public
   GET /taxonomy returning domains, jobs and display labels.

2. Alembic migration. Add to tools:
   - domain (nine slugs), jobs (list of taxonomy slugs only)
   - pricing_model: free | freemium | free_trial | paid | open_source | unknown
   - has_free_tier (bool|null), free_tier_summary (max 140), free_tier_limits,
     starting_price_monthly_usd (number|null), pricing_notes, credit_card_required (bool|null),
     watermark_on_free (bool|null), commercial_use_on_free (bool|null)
   - pricing_url, pricing_checked_at
   - platforms (list), skill_level (beginner | intermediate | advanced | all)
   - tagline (max 90), summary, how_it_helps, pros (max 3), cons (max 3)
   - logo_url, og_image_url (our own storage URLs)
   - evidence (JSON: field -> {source_url, quote, checked}), review_flags (list of strings),
     official_domains (list), research_provider, researched_at, verified_by, is_pick (bool)
   Keep existing columns (affiliate_url, prompt_style, input_types, output_types, status,
   verified_at, link_status, sources, research_notes). In the UI, replace the old free-text
   `category` with `domain`; keep the DB column.
   Statuses: draft | researched | verified | hidden.

3. Existing tools: set status to draft (keep affiliate_url and URLs) so they are re-imported.
   Do not delete data.

4. Pydantic schemas: ToolPublicResponse exposes the display fields and go_path, never
   affiliate_url. Admin schemas expose everything. Validate jobs against the taxonomy.

5. Planner scoring uses EXACT job-slug matches from tools.jobs. Remove text-overlap job matching.

Done when: migrations apply on empty and existing databases, /taxonomy works, unknown job slugs
are rejected, and scoring tests pass with slug matching.
```

### C2: Card importer (replaces any Perplexity API integration)

```text
C2: Provider-agnostic card importer. Research is done outside the app and imported as JSON.
All claims are re-validated in code.

1. Config: do NOT require PERPLEXITY_API_KEY. Keep services/research/provider.py as an interface
   so an API provider can be added later; implement only the importer now.

2. Importer
   - POST /admin/tools/import-cards (admin only) takes {"cards": [...]} (section 3 shape), plus
     CLI `python -m app.scripts.import_cards cards.json [--expect tools.csv]`. Add an admin UI page
     with a paste/upload box and a per-card result list.
   - Validate with fixed Pydantic models (no dict[str, Any] for structured fields) and enforce all
     limits in section 3. prompt_style.rules accepts a string or list and is normalized to a list.
   - Upsert by case-insensitive name or by official_url. Create or update as status=researched.
     Preserve affiliate_url, verified fields and status history. If a verified tool's pricing fields
     change, set it back to researched and add a review flag. Ignore any affiliate_url, status,
     verified or logo fields in the imported JSON.
   - Registrable domains of official_url, pricing_url and docs_url are always official. The tool's
     official_domains list (from the CSV or admin UI) adds extras (for example claude.ai, claude.com,
     code.claude.com and support.claude.com for Claude Code).
   - --expect: compare the imported names with a seed CSV and list tools missing from the JSON, so
     skipped tools are obvious.

3. Validation (in code)
   a) domain must be a taxonomy domain. Drop job slugs not in the taxonomy and flag the card; if
      none remain, mark it needs-review.
   b) Evidence: source_url must be on an official domain (subdomains allowed). Otherwise discard
      that evidence, set the claimed field to null, and add "evidence off-domain: <field>".
   c) Quote check: fetch each evidence source_url with the SSRF-safe fetcher and confirm the quote
      appears in the page text. Normalize both sides: case-insensitive, collapse whitespace and
      newlines, and strip markdown and table symbols (| # * _ ` [ ] ( ) check marks, bullets).
      Store evidence checked = true / false / unknown (unknown if the page cannot be fetched or is
      JavaScript-rendered). false adds a review flag. Never block the import on unknown.
   d) Reject range or vague price claims ("typically", "approx", "$10-50").
   e) Consistency rules; violations add review flags:
      - pricing_model free or freemium requires has_free_tier = true
      - pricing_model paid requires has_free_tier = false (or null)
      - pricing_model free_trial requires has_free_tier = false (or null)
      - has_free_tier = true requires a non-empty free_tier_summary
      - paid/freemium with starting_price_monthly_usd null gets a flag
   f) Cross-check with Gemini: send the card plus the fetched page text and ask for contradictions.
      Explicitly check that has_free_tier and pricing_model describe THIS product (not another plan
      or product from the same vendor) and that summary, pros and cons agree with the pricing fields.
      Add each contradiction to review_flags.
   g) Fetch logo and og:image from the official site (SSRF-safe, type and size checked) and store
      them in Supabase Storage server-side (service-role key, never in the frontend).
   h) Each string in unknowns becomes a review flag; strings starting with "check:" are shown as notes.

4. Return a summary: created, updated, rejected counts, the missing-tool list, and per-card flags.

5. Tests: off-domain evidence removed, unknown job slugs dropped, a fake quote flagged, range
   pricing rejected, quote check tolerant of markdown/table symbols, consistency rules flagged,
   upsert preserves affiliate_url, a verified tool drops to researched when pricing changes,
   --expect lists missing tools, and the endpoint is admin only.

Done when: pasting a valid cards.json creates researched cards with evidence status and flags,
and untrustworthy fields never reach the public directory.
```

### C3: Admin review and freshness

```text
C3: Admin review screen and freshness.

1. Review screen per tool: show each critical field (pricing_model, has_free_tier,
   free_tier_summary, starting price, credit card, commercial use, watermark, skill level, platforms)
   next to its evidence quote and source link with a checked indicator (green, red, grey). Show
   review_flags prominently. Explanations, jobs, domain and official_domains are editable. Logo
   preview with an upload override.

2. Verify is disabled until: domain set; at least one valid job slug; pricing_model set (not
   unknown); free-tier fields set when pricing_model is free/freemium/free_trial; every pricing
   field has evidence; all explanation fields within limits; link reachable; all review flags
   marked reviewed. The screen lists which rule is failing. Verify sets verified_at, verified_by
   and pricing_checked_at.

3. Pick toggle (is_pick) per tool, allowed only for verified tools.

4. Freshness
   - GET /admin/tools/stale: verified tools whose pricing_checked_at is older than 30 days.
   - Recheck: the admin pastes a fresh card JSON for the tool (same importer) and sees a
     field-by-field diff before applying.
   - POST /admin/jobs/check-links protected by a CRON_SECRET header for a Render cron job
     (document in DEPLOY.md). Dead links set link_status=dead and hide the tool.

5. Public cards show "Verified <Mon YYYY>" from verified_at. There is no "Tested" badge.

Done when: an admin can review an imported tool, see where each claim came from, verify it, and
see stale tools in a list.
```

### C4: Directory UX

```text
C4: Public directory redesign. Keep the existing visual style.

1. Browsing: tabs for the nine domains (from /taxonomy), then job chips for the selected domain.
   Remove the old "AI ..." category pills.
2. Filters: pricing (Free, Freemium, Free trial, Paid, Open source), toggles for "Has free tier",
   "No credit card", "Commercial use on free plan", plus search (name, tagline, jobs). Sort:
   Pathwise picks first, then name.
3. Card: logo (initials fallback, lazy loaded, alt text), name, tagline, price badge with the
   one-line free_tier_summary, up to 3 job chips, Open tool (through /go), Card info.
4. Card info modal: summary, how it helps, pros and cons, pricing details with "checked on <date>"
   and a source link, free-tier limits, platforms, skill level, prompt style with Copy Example
   Prompt, input/output types, best for / not for.
5. "Pathwise pick" badge for is_pick; "Verified <Mon YYYY>" badge for verified tools.
6. Keep the "May include an affiliate link" note next to Open tool.
7. Empty, loading and error states; mobile layout to 360px; keyboard accessible; fast with 100 tools.

Done when: the directory shows logos, price badges, explanations and domain tabs for all verified
tools and the filters work together.
```

### C5: Interview and planner for any creator

```text
C5: Interview and planner use the taxonomy and the budget rule.

1. Interview: first detect the domain(s) from the goal. Keep the 0-5 question rule. Ask domain-aware
   questions (video: length, style, voiceover or on-camera; audio: genre, vocals or instrumental;
   software: stack and deploy target; writing: audience and channel; design: use case and brand).
   Always capture, if not known: budget_preference (free_only | low | flexible), skill_level, and
   needs_commercial_use (yes | no | unknown). Update the brief schema and frontend types.

2. Planner: the LLM chooses 1-6 jobs ONLY from taxonomy slugs for the detected domains. Code
   shortlists tools by exact slug, then:
   - free_only: exclude tools where has_free_tier is not true (hard rule). If a job is left with no
     tool, create the standard "No verified tool yet. Come back later." step with a note that no free
     option exists yet.
   - needs_commercial_use == yes: with free_only, exclude tools where commercial_use_on_free is false;
     otherwise show a warning only.
   - Everything else (skill level, stack mentions, input/output match, pick flag) ranks.
   - Tools whose pricing_checked_at is older than 60 days get a small penalty and a
     "pricing may have changed" warning.

3. Workflow response: cost_summary {mode: "free" | "may_cost", estimated_monthly_usd, notes[]},
   computed in code from stored tool fields (not by the LLM), and per step free_tier_note.

4. Frontend: show the cost summary at the top of the workflow and the free-tier note under each tool.

Done when: a "free only" goal never returns a paid-only tool, the cost summary comes from stored
tool data, and tests cover every branch.
```

### C6: Seeding and docs

```text
C6: Seed the catalog.

1. Update scripts/seed_candidates.py. CSV columns: name, domain, url, docs_url, pricing_url,
   affiliate_url, official_domains (use "|" between domains). Validate domain against the taxonomy.
   Validate affiliate_url with the existing validator. Idempotent. Creates DRAFT tools only. Remove the
   old --research flag (research now comes through the importer). Print a summary table.
2. Replace the repo root tools.csv with the wave 1 list in section 6.
3. Update docs/DEPLOY.md: the Supabase Storage bucket, CRON_SECRET, and a first-run checklist
   (migrate, seed, import cards, review, verify, mark picks).
4. Add docs/CATALOG.md: the taxonomy, status levels, what "Verified" means, the 30-day pricing recheck
   rule, and the research workflow (run the Perplexity prompt per domain, audit, import).

Done when: seeding creates drafts, importing cards.json upgrades them to researched with evidence,
and the DEPLOY.md checklist works from a clean setup.
```

### C7 (optional, after the beta starts): usage signals

```text
C7: After "Mark finished", ask "Did this step work?" (worked | partly | didn't) with an optional note.
Store in step_feedback. Admin metrics show per-tool success rates. Public cards show
"Used in N workflows" only once a tool has at least 10 feedback entries. Never show individual
notes publicly.
```

---

## 5. Order of work

C0 -> C1 -> C2 -> C3 -> C6 (seed + import the first cards) -> C4 -> C5 -> C7.
Commit after each slice. Paste the slice summary back for review before starting the next.

## 6. Wave 1 seed list (44 tools)

Save as the repo root `tools.csv`. `official_domains` uses `|`. Some docs URLs may be wrong; the link checker flags dead ones.

```csv
name,domain,url,docs_url,pricing_url,affiliate_url,official_domains
Cursor,software,https://cursor.com,https://cursor.com/docs,https://cursor.com/pricing,,cursor.com
Claude Code,software,https://claude.com/product/claude-code,https://code.claude.com/docs/en/overview,https://claude.com/pricing,,claude.com|claude.ai|code.claude.com|support.claude.com|docs.claude.com|anthropic.com
GitHub Copilot,software,https://github.com/features/copilot,https://docs.github.com/en/copilot,https://github.com/features/copilot/plans,,github.com|docs.github.com|github.blog
Google Antigravity,software,https://antigravity.google,,,,antigravity.google
Windsurf,software,https://windsurf.com,https://docs.windsurf.com,,,windsurf.com
GitHub,software,https://github.com,https://docs.github.com,https://github.com/pricing,,github.com|docs.github.com
Replit,builders,https://replit.com,https://docs.replit.com,https://replit.com/pricing,,replit.com
Lovable,builders,https://lovable.dev,https://docs.lovable.dev,,,lovable.dev
Bolt.new,builders,https://bolt.new,https://support.bolt.new,,,bolt.new|stackblitz.com
v0,builders,https://v0.app,https://v0.app/docs,,,v0.app|vercel.com
Framer,builders,https://www.framer.com,https://www.framer.com/help,,,framer.com
Figma,design,https://www.figma.com,https://help.figma.com,https://www.figma.com/pricing,,figma.com
Canva,design,https://www.canva.com,https://www.canva.com/help,https://www.canva.com/pricing,,canva.com
Adobe Firefly,design,https://firefly.adobe.com,,,,adobe.com
Midjourney,design,https://www.midjourney.com,https://docs.midjourney.com,,,midjourney.com
Ideogram,design,https://ideogram.ai,,,,ideogram.ai
Gamma,design,https://gamma.app,,,,gamma.app
Runway,video,https://runwayml.com,https://help.runwayml.com,https://runwayml.com/pricing,,runwayml.com
CapCut,video,https://www.capcut.com,,,,capcut.com
Descript,video,https://www.descript.com,https://help.descript.com,,,descript.com
HeyGen,video,https://www.heygen.com,https://help.heygen.com,,,heygen.com
Luma Dream Machine,video,https://lumalabs.ai,,,,lumalabs.ai
Kling AI,video,https://klingai.com,,,,klingai.com
Suno,audio,https://suno.com,,https://suno.com/pricing,,suno.com
Udio,audio,https://www.udio.com,,,,udio.com
ElevenLabs,audio,https://elevenlabs.io,https://elevenlabs.io/docs,,,elevenlabs.io
Audacity,audio,https://www.audacityteam.org,https://support.audacityteam.org,,,audacityteam.org
Otter.ai,audio,https://otter.ai,https://help.otter.ai,,,otter.ai
ChatGPT,writing,https://chatgpt.com,https://help.openai.com,,,chatgpt.com|openai.com|help.openai.com
Claude,writing,https://claude.ai,https://support.claude.com,https://claude.com/pricing,,claude.ai|claude.com|support.claude.com|anthropic.com
Gemini,writing,https://gemini.google.com,,,,gemini.google.com|google.com|ai.google.dev|support.google.com
Grammarly,writing,https://www.grammarly.com,https://support.grammarly.com,,,grammarly.com
Perplexity,research,https://www.perplexity.ai,https://docs.perplexity.ai,,,perplexity.ai
NotebookLM,research,https://notebooklm.google,,,,notebooklm.google|google.com|support.google.com
Notion,research,https://www.notion.com,https://www.notion.com/help,https://www.notion.com/pricing,,notion.com
Obsidian,research,https://obsidian.md,https://help.obsidian.md,,,obsidian.md
Supabase,deploy_backend,https://supabase.com,https://supabase.com/docs,https://supabase.com/pricing,,supabase.com
Vercel,deploy_backend,https://vercel.com,https://vercel.com/docs,https://vercel.com/pricing,,vercel.com
Cloudflare,deploy_backend,https://www.cloudflare.com/developer-platform,https://developers.cloudflare.com,,,cloudflare.com
Render,deploy_backend,https://render.com,https://render.com/docs,https://render.com/pricing,,render.com
Netlify,deploy_backend,https://www.netlify.com,https://docs.netlify.com,https://www.netlify.com/pricing,,netlify.com
Stripe,freelance_ops,https://stripe.com,https://docs.stripe.com,https://stripe.com/pricing,,stripe.com
Calendly,freelance_ops,https://calendly.com,https://help.calendly.com,,,calendly.com
Loom,freelance_ops,https://www.loom.com,https://support.atlassian.com/loom,,,loom.com|atlassian.com
```
