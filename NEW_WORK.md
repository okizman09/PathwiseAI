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

## Reused from before the event
- Auth, quotas, catalog and importer, planner scoring, existing UI
