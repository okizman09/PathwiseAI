# New work during the hackathon (Oct 26 to Nov 4, 2026)

This repo is the pre-existing Pathwise project and the rebuild is happening
in place (no separate import commit). Everything under "Built during the
event" was built during the hackathon window.

## Built during the event
- T1: Meta hello-world probe (`backend/scripts/meta_hello.py`) + `openai` dependency; gate passed, structured method `json_schema` (base history up to f49c531; exact hash TBD (paste full git log --oneline))
- T2: Meta LLM module (`generate_structured`/`generate_text`) next to Gemini code + `MODEL_API_KEY`/`META_*` settings + Meta models check + 7 mocked tests; suite 141 green (base history up to f49c531; exact hash TBD (paste full git log --oneline))
- T3: Migrated all call sites (interview, plan, prompts, both extractors) to Meta; deleted Gemini code, settings, dependency; suite 141 green (base history up to f49c531; exact hash TBD (paste full git log --oneline))
- T4: Catalog Meta fields (ecosystem/kind/model_id/api_snippet) + migration + importer mappings + ecosystem filter; suite 144 green (46cb4fc)
- T5: Imported 9 Meta cards (IDs 115-123); facts/snippets/pricing verified against dev.meta.ai, all 9 VERIFIED via app rules; logos + og previews resolved (2b60a17)
- T6: Meta-aware planner (tool context fields, prompt rules, invented-ID post-check) + is_pick on Spark/Voice/Image; suite 147 green (c0d30c6)
- T7: Smoke harness (scripts/smoke_plan.py + shared planner/checks.py + offline pytest); live 8/8 green + pool_pre_ping fix (7d41b2d (shared with T8))
- T8: Frontend Meta surfaces (filter chip, badges, model detail section, step snippet); tsc + build green (7d41b2d)
- Batch follow-up 1: dynamic step content (content_type/action_steps, rule 8, migration e5f6a7b8c9d0); suite 156 green, tsc + build green (77a719b)
- Batch follow-up 2: Models/Meta browse views (directory tabs + modal tabs, collection filters, modal logo thumbnails + Meta badge); tsc + build green (77a719b + d085140 (tabs + modal))
- Batch follow-up 3: landing demo-goal example (voice notes to structured orders, 4 stages incl. Meta models + Supabase setup steps) + light polish; tsc + build green (77a719b)
- Batch follow-up 4: catalog audit module + CLI (19 issue codes, 9 tests) + logo/og backfill CLI; live audit 123 tools; suite 165 green (77a719b)
- Batch follow-up 5: catalog cleanup (affiliate notes, Catalog v3 pill, verified-month badges -> plain Verified, workspace goal guidance); tsc + build green (77a719b)
- Batch follow-up 6: marked 6 model-like tools with kind (Jukebox/AudioCraft/CodeT5 open_weight, DALL-E/WaveNet runnable, Hugging Face platform); Models view now 15 cards (live DB only, no commit)
- Batch follow-up 7: fixed Hugging Face (domain research, job research_topic, model-hub tagline/best_for); tagline script gained --exclude-ids; ruff clean (d085140 (tooling) + live DB)
- Batch follow-up 8: researched + imported Manus (ID 124, builders, freemium $20+, official help-center evidence x3 matched, logo+og, VERIFIED); backfill 114 ok / 0 failed; catalog now 124 tools (77a719b)
- Batch follow-up 9: landing beautification (hairline grid, animated route + waypoint SVG, entrance motion, section anchors); same theme, single accent color; tsc + build green (77a719b)
- Batch follow-up 10: tagline rewrite executed by user (114/114 saved incl. 4-ID rerun); fixed freelancer substring false-rejects (word-boundary ban); restored curated Manus tagline (live DB only, no commit)
- Batch follow-up 11: nav labels (Discover -> Explore tools, Example -> Sample workflow incl. mobile/footer/eyebrow/mockup); tsc + build green (d085140)
- Batch follow-up 12: fixed plan truncation (synthesis max_output_tokens 4096 -> 8192; action_steps outgrew budget); ruff + 13 step tests green, no new test (config value) (d085140)
- Batch follow-up 13: interview loaders (spinner session gate, question skeleton, thinking dots; dropped loading texts); tsc + build green (d085140)
- Batch follow-up 14: honest cost summary (pricing_complete flag, estimate wording, note dedupe) + affiliate line removed from workspace + verified Lovable/Firebase pricing; suite 166 green, tsc + build green (d085140)
- Batch follow-up 15: product-name capture (brief.product_name, interview rule 4, planner rule 9, brief card display, 4 contract tests); suite 170 green, tsc + build green (d085140)
- Batch follow-up 16: native-coverage jobs rule (skip redundant hosting/database steps, Lovable+Supabase example) + Lovable/Supabase summaries; suite 171 green (d085140)

- T9 (backend): live step runs (StepRun model + migration f6a7b8c9d0e1, services/run.py eligibility+prompt+execute, run endpoints, step_run quota 10/day, run caps); 7 run tests green, full suite 178 green, alembic head f6a7b8c9d0e1 (02e1643)
- T9 (frontend): Run button + live output panel (copy/.md download, tokens/ms) on runnable prompt steps; tsc + prettier-region-clean + build green (02e1643)
- Landing sample tightening: runnable flags + "Runs live in the workspace" caption on Transcribe/Structure stages, Store step cites builder-native Supabase integration, section copy mentions live runs; tsc + build green (02e1643)
- Batch follow-up 17: corrected Gretel (synthetic training-data generation, was "analyze data") + MOSTLY AI (privacy-safe synthetic tabular data, verified via web); left jobs=analyze_data (no synthesis slug, taxonomy frozen); K2view/Julius checked, no change; live audit re-run, standing gaps unchanged (live DB only, no commit)

- Security fix: enabled RLS on all 11 public tables (migration a7b8c9d0e1f2, Postgres-guarded); verified frontend is auth-only and backend bypasses RLS, backend reads confirmed post-fix (319c005)
- Batch follow-up 18: free-only budget hint (shows when budget is free_only and zero steps runnable; cites 10 runs/day limit); tsc + build green, no frontend test harness (319c005)
- Batch follow-up 19: step-count pluralization ("1 Sequenced Action Step"); tsc + build green (3a8b6d5)
- Perf batch: auth last_seen throttled to 15 min + refresh dropped; hydrate tool batching (1 query vs N); /tools 60 s response cache + invalidation on 9 admin mutations; async-to-def on pure-DB endpoints; directory staleTime 5 min; suite 181 green, ruff clean (3a8b6d5)
- Refresh batch: workspace snapshots goal/answers/question/brief/workflowId to localStorage, restores on refresh, syncs ?load= on generate, reset clears both, getMe failure stays on page with Retry unless logged out; tsc + build green (3a8b6d5)
- LLM latency batch (speed only): SDK max_retries 1→0, app layer keeps its single retry (worst case 4→2 attempts); verified prompts already minimal (shortlist top-4, ~7 KB synthesis input, no parallelizable calls); reasoning-effort probe written for user run; suite 181 green, ruff clean (3a8b6d5)
- Reasoning effort (speed only): probe proved effort=low honored (4.4→2.9 s, identical output); opt-in reasoning_effort mechanism in generate_structured + 2 passthrough tests, default sends nothing; call-site wiring pending schema-combo probe; suite 183 green, ruff clean (3a8b6d5)
- Reasoning effort wiring (speed only): schema-combo probe OK; effort=low on interview + job-plan + synthesis calls; fakes updated + wiring assertions (plan 2-call, interview); runs/extractors stay default; suite 184 green, ruff clean (3a8b6d5)
- Empty-run fix: RUN_MAX_OUTPUT_TOKENS 2048→8192 (reasoning ate the budget, run #1 returned 0 chars); empty output now fails with empty_response + quota refund (shared persist helper); refunded run #1's quota; 1 new test; suite 185 green, ruff clean (3a8b6d5)
- Run button moved from bottom action row to prompt card header (same behavior); tsc + build green (3a8b6d5)
- Live output pretty-print: JSON auto-detected, indented + highlighted (theme hues, no new libs); plain text unchanged; copy/.md still use raw text; tsc + build green (3a8b6d5)
- T10: README rewrite (Meta provider/directory/planner, run instructions, env, tests, limitations, adapted roadmap); deploy files fixed for Meta (render.yaml keys, DEPLOY.md steps, .env.example run budget); SUBMISSION.md drafted with form answers; NEW_WORK finalized (3a8b6d5 + 96febbe)
- Review follow-up: repo clutter removed (mockups/, files.zip, screenshot, stray docs txt, dupe data/cards.json); global step-run cap 200/day across users (spend guard) + test; render.yaml/.env.example updated; suite 186 green, ruff clean (96febbe)
- Deploy fix: pinned openai>=1.66.0,<2 (Render resolved untested v3.45; local suite runs v1); backend live at pathwiseai-gxo7.onrender.com; frontend VITE_API_URL repointed qkf1->gxo7 (8ae9b1c)
- Prod API fallback fix: frontend getApiBaseUrl hardcoded fallback still pointed at deleted qkf1 backend (no build-time VITE_API_URL set); repointed both fallbacks to gxo7 (commit pending)
- Run-button fix: planner wrote synthesis content_type straight to DB; a 'steps'-tagged step holding only a prompt lost can_run (tutoring goal, no Run on Spark step); post-check now coerces content_type against the populated field both directions + 2 e2e fake-LLM tests (commit pending)

## Reused from before the event
- Auth, quotas, catalog and importer, planner scoring, existing UI
