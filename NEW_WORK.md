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

## Reused from before the event
- Auth, quotas, catalog and importer, planner scoring, existing UI
