# New work during the hackathon (Oct 26 to Nov 4, 2026)

This repo is the pre-existing Pathwise project and the rebuild is happening
in place (no separate import commit). Everything under "Built during the
event" was built during the hackathon window.

## Built during the event
- T1: Meta hello-world probe (`backend/scripts/meta_hello.py`) + `openai` dependency; gate passed, structured method `json_schema` (commit pending)
- T2: Meta LLM module (`generate_structured`/`generate_text`) next to Gemini code + `MODEL_API_KEY`/`META_*` settings + Meta models check + 7 mocked tests; suite 141 green (commit pending)
- T3: Migrated all call sites (interview, plan, prompts, both extractors) to Meta; deleted Gemini code, settings, dependency; suite 141 green (commit pending)
- T4: Catalog Meta fields (ecosystem/kind/model_id/api_snippet) + migration + importer mappings + ecosystem filter; suite 144 green (commit pending)
- T5: Imported 9 Meta cards (IDs 115-123); facts/snippets/pricing verified against dev.meta.ai, all 9 VERIFIED via app rules; logos + og previews resolved (commit pending)
- T6: Meta-aware planner (tool context fields, prompt rules, invented-ID post-check) + is_pick on Spark/Voice/Image; suite 147 green (commit pending)
- T7: Smoke harness (scripts/smoke_plan.py + shared planner/checks.py + offline pytest); live 8/8 green + pool_pre_ping fix (commit pending)
- T8: Frontend Meta surfaces (filter chip, badges, model detail section, step snippet); tsc + build green (commit pending)
- Batch follow-up 1: dynamic step content (content_type/action_steps, rule 8, migration e5f6a7b8c9d0); suite 156 green, tsc + build green (commit pending)
- Batch follow-up 2: Models/Meta browse views (directory tabs + modal tabs, collection filters, modal logo thumbnails + Meta badge); tsc + build green (commit pending)
- Batch follow-up 3: landing demo-goal example (voice notes to structured orders, 4 stages incl. Meta models + Supabase setup steps) + light polish; tsc + build green (commit pending)
- Batch follow-up 4: catalog audit module + CLI (19 issue codes, 9 tests) + logo/og backfill CLI; live audit 123 tools; suite 165 green (commit pending)
- Batch follow-up 5: catalog cleanup (affiliate notes, Catalog v3 pill, verified-month badges -> plain Verified, workspace goal guidance); tsc + build green (commit pending)
- Batch follow-up 6: marked 6 model-like tools with kind (Jukebox/AudioCraft/CodeT5 open_weight, DALL-E/WaveNet runnable, Hugging Face platform); Models view now 15 cards (commit pending: data-only, no code change)
- Batch follow-up 7: fixed Hugging Face (domain research, job research_topic, model-hub tagline/best_for); tagline script gained --exclude-ids; ruff clean (commit pending)
- Batch follow-up 8: researched + imported Manus (ID 124, builders, freemium $20+, official help-center evidence x3 matched, logo+og, VERIFIED); backfill 114 ok / 0 failed; catalog now 124 tools (commit pending)
- Batch follow-up 9: landing beautification (hairline grid, animated route + waypoint SVG, entrance motion, section anchors); same theme, single accent color; tsc + build green (commit pending)
- Batch follow-up 10: tagline rewrite executed by user (114/114 saved incl. 4-ID rerun); fixed freelancer substring false-rejects (word-boundary ban); restored curated Manus tagline (commit pending)
- Batch follow-up 11: nav labels (Discover -> Explore tools, Example -> Sample workflow incl. mobile/footer/eyebrow/mockup); tsc + build green (commit pending)
- Batch follow-up 12: fixed plan truncation (synthesis max_output_tokens 4096 -> 8192; action_steps outgrew budget); ruff + 13 step tests green, no new test (config value) (commit pending)
- Batch follow-up 13: interview loaders (spinner session gate, question skeleton, thinking dots; dropped loading texts); tsc + build green (commit pending)
- Batch follow-up 14: honest cost summary (pricing_complete flag, estimate wording, note dedupe) + affiliate line removed from workspace + verified Lovable/Firebase pricing; suite 166 green, tsc + build green (commit pending)
- Batch follow-up 15: product-name capture (brief.product_name, interview rule 4, planner rule 9, brief card display, 4 contract tests); suite 170 green, tsc + build green (commit pending)
- Batch follow-up 16: native-coverage jobs rule (skip redundant hosting/database steps, Lovable+Supabase example) + Lovable/Supabase summaries; suite 171 green (commit pending)

- T9 (backend): live step runs (StepRun model + migration f6a7b8c9d0e1, services/run.py eligibility+prompt+execute, run endpoints, step_run quota 10/day, run caps); 7 run tests green, full suite 178 green, alembic head f6a7b8c9d0e1 (commit pending)
- T9 (frontend): Run button + live output panel (copy/.md download, tokens/ms) on runnable prompt steps; tsc + prettier-region-clean + build green (commit pending)
- Landing sample tightening: runnable flags + "Runs live in the workspace" caption on Transcribe/Structure stages, Store step cites builder-native Supabase integration, section copy mentions live runs; tsc + build green (commit pending)
- Batch follow-up 17: corrected Gretel (synthetic training-data generation, was "analyze data") + MOSTLY AI (privacy-safe synthetic tabular data, verified via web); left jobs=analyze_data (no synthesis slug, taxonomy frozen); K2view/Julius checked, no change; live audit re-run, standing gaps unchanged (commit pending: data-only, no code change)

- Security fix: enabled RLS on all 11 public tables (migration a7b8c9d0e1f2, Postgres-guarded); verified frontend is auth-only and backend bypasses RLS, backend reads confirmed post-fix (commit pending)
- Batch follow-up 18: free-only budget hint (shows when budget is free_only and zero steps runnable; cites 10 runs/day limit); tsc + build green, no frontend test harness (commit pending)
- Batch follow-up 19: step-count pluralization ("1 Sequenced Action Step"); tsc + build green (commit pending)
- Perf batch: auth last_seen throttled to 15 min + refresh dropped; hydrate tool batching (1 query vs N); /tools 60 s response cache + invalidation on 9 admin mutations; async-to-def on pure-DB endpoints; directory staleTime 5 min; suite 181 green, ruff clean (commit pending)
- Refresh batch: workspace snapshots goal/answers/question/brief/workflowId to localStorage, restores on refresh, syncs ?load= on generate, reset clears both, getMe failure stays on page with Retry unless logged out; tsc + build green (commit pending)
- LLM latency batch (speed only): SDK max_retries 1→0, app layer keeps its single retry (worst case 4→2 attempts); verified prompts already minimal (shortlist top-4, ~7 KB synthesis input, no parallelizable calls); reasoning-effort probe written for user run; suite 181 green, ruff clean (commit pending)
- Reasoning effort (speed only): probe proved effort=low honored (4.4→2.9 s, identical output); opt-in reasoning_effort mechanism in generate_structured + 2 passthrough tests, default sends nothing; call-site wiring pending schema-combo probe; suite 183 green, ruff clean (commit pending)
- Reasoning effort wiring (speed only): schema-combo probe OK; effort=low on interview + job-plan + synthesis calls; fakes updated + wiring assertions (plan 2-call, interview); runs/extractors stay default; suite 184 green, ruff clean (commit pending)
- Empty-run fix: RUN_MAX_OUTPUT_TOKENS 2048→8192 (reasoning ate the budget, run #1 returned 0 chars); empty output now fails with empty_response + quota refund (shared persist helper); refunded run #1's quota; 1 new test; suite 185 green, ruff clean (commit pending)
- Run button moved from bottom action row to prompt card header (same behavior); tsc + build green (commit pending)
- Live output pretty-print: JSON auto-detected, indented + highlighted (theme hues, no new libs); plain text unchanged; copy/.md still use raw text; tsc + build green (commit pending)
- T10: README rewrite (Meta provider/directory/planner, run instructions, env, tests, limitations, adapted roadmap); deploy files fixed for Meta (render.yaml keys, DEPLOY.md steps, .env.example run budget); SUBMISSION.md drafted with form answers; NEW_WORK finalized (commit pending)

## Reused from before the event
- Auth, quotas, catalog and importer, planner scoring, existing UI
