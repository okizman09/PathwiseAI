# Pathwise AI: Technical Spec for the Hackathon Build

Companion to `PRD.md`. Written against the actual repo (FastAPI backend, Supabase/Postgres or SQLite, React frontend with TanStack routes). Muse Code must still inspect the code before editing; where this spec names a file or function, confirm it first.

## 1. What exists today (verified in the repo)

- Backend: `backend/app/` with `routers/`, `services/`, `models/`, `schemas/`, `taxonomy/`, `scripts/`, Alembic migrations in `backend/alembic/versions/`.
- Planning flow: `services/interview.py` (up to 5 turns, builds a product brief) then `services/plan.py` (the model picks 1 to 6 jobs from the taxonomy, `services/planner/scoring.py` shortlists tools with deterministic rules, the model assigns tools and writes prompts via `services/prompts.py`).
- Catalog: `models/tool.py` (`Tool` with jobs, platforms, `prompt_style`, `evidence`, `sources`, `status` draft/researched/verified/hidden, `is_pick`), importer `services/importer.py` with `schemas/card_import.py` (`CardImport`), CLI `scripts/import_cards.py`.
- Taxonomy: nine domains and fixed job slugs in `taxonomy/taxonomy.yaml`. Do not change it.
- Gemini coupling: `services/llm.py` (`get_gemini_client`, `generate_content_resilient`, `extract_tool_card_from_docs`), call sites in `services/interview.py`, `services/plan.py`, `services/prompts.py`; config in `core/config.py` (`GEMINI_API_KEY`, `GEMINI_MODEL`); `scripts/check_connections.py`; test mocks in `tests/conftest.py` and `tests/test_beta_readiness.py`. Run `grep -rIl "generate_content_resilient\|get_gemini_client\|GEMINI" backend` to confirm the full list.
- Existing tests: 134 passed when run on a fresh install.

## 2. Change A: Meta LLM module (FR-1)

Rework `services/llm.py`. Keep the file path so imports stay short. Sequence: Task T2 adds the new Meta functions next to the old Gemini ones so the test suite stays green; Task T3 moves the call sites and then deletes the Gemini code.

```python
# app/services/llm.py (target interface)
from pydantic import BaseModel

async def generate_structured(
    *, system: str, user: str, schema: type[BaseModel],
    temperature: float = 0.2, max_output_tokens: int | None = None,
) -> BaseModel: ...

async def generate_text(
    *, system: str | None, user: str,
    model: str | None = None, max_output_tokens: int | None = None,
) -> "TextResult": ...   # TextResult: text, model, input_tokens, output_tokens
```

Implementation rules:

- Client: `AsyncOpenAI(api_key=settings.MODEL_API_KEY, base_url=settings.META_BASE_URL, max_retries=1, timeout=settings.LLM_TIMEOUT_SECONDS)`.
- Model: `settings.META_MODEL` (default `muse-spark-1.3`). No fallback to another model. If the model is unavailable, raise the existing sanitized error type.
- Calls use the Responses API: `client.responses.create(model=..., instructions=system, input=user, ...)`; read `response.output_text`.
- Structured output, try in this order and keep whichever T1 proves works on your key:
  1. `text={"format": {"type": "json_schema", "name": schema.__name__, "schema": schema.model_json_schema(), "strict": True}}`
  2. `text={"format": {"type": "json_object"}}` with the JSON schema written into `instructions`, then `schema.model_validate_json(...)`. On a validation error, retry once on the same model with the error message appended. (Meta's own workshop code uses `json_object` this way.)
- Keep the existing retry rule: two attempts total on transient errors, same model.
- Never log the API key, the full prompt of user content, or the raw provider error. Map provider errors to the existing `core/errors.py` types.
- Keep `extract_tool_card_from_docs` working on the new module (the importer and admin research use it).

Config (`core/config.py`, `.env.example`, any settings list that names `GEMINI_API_KEY`):

| Variable | Default | Notes |
|---|---|---|
| `MODEL_API_KEY` | none | Meta Model API key; required |
| `META_BASE_URL` | `https://api.meta.ai/v1` | |
| `META_MODEL` | `muse-spark-1.3` | |
| `LLM_TIMEOUT_SECONDS` | `90` | |

Remove the `GEMINI_*` settings. Update `scripts/check_connections.py` to call `GET {base_url}/models` and report whether `META_MODEL` is available.

## 3. Change B: migrate call sites (FR-1)

| File | Work |
|---|---|
| `services/interview.py` | Replace Gemini calls with `generate_structured`; keep the 5-turn limit and the sanitizer |
| `services/plan.py` | Same, for job selection and tool assignment |
| `services/prompts.py` | Same, for prompt synthesis (largest file) |
| `services/research/extractor.py` and `services/llm.py` | Keep `extract_tool_card_from_docs` working |
| `tests/conftest.py`, `tests/test_beta_readiness.py` and any test patching the old functions | Patch `generate_structured` / `generate_text` instead |

Do not change prompts' wording in this task, only the call mechanics. Prompt changes come in Change E.

## 4. Change C: catalog fields for Meta (FR-3)

Alembic migration (additive, nullable): add to `tools`:

| Column | Type | Meaning |
|---|---|---|
| `ecosystem` | `String(50)`, indexed | `meta` for the Meta collection |
| `kind` | `String(30)` | `runnable`, `open_weight`, `developer_tool`, `platform` |
| `model_id` | `String(100)` | exact API model ID when one exists |
| `api_snippet` | `Text` | the how-to-call code, written by you, not generated |

Also:

- Add the four fields to `models/tool.py`, `schemas/tool.py` (`ToolBase` and read schemas) and the admin create/update schemas.
- `routers/tools.py`: add an optional `ecosystem` query filter on the public list endpoint.
- `schemas/card_import.py`: add the same four fields, plus `docs_url`, as optional on `CardImport`, and map them in `services/importer.py` (both create and update paths). The seed file already includes `docs_url`; without this mapping it is silently dropped.
- Existing tools keep null values; nothing else changes.

## 5. Change D: Meta seed cards (FR-3)

File: `backend/data/meta_cards.json` (a JSON list in the `CardImport` format, same shape as `backend/cards.json`).

Load with `python -m app.scripts.import_cards data/meta_cards.json`. Then, for each card, open the official docs page, check the facts, fill anything marked unknown, and press Verify in the admin console. The planner only uses verified cards.

Rules:

- Use only existing taxonomy job slugs (at most 5 per card). Segmentation has no slug, so SAM 3.1 uses `edit_image` and carries a note.
- No pricing claims. `pricing_model` is `unknown` until you check Meta's pricing page.
- Evidence quotes are optional. If you add one, it must be real text from an official page (the importer verifies quotes against the page).
- `api_snippet` is hand-written and short. Example for a text model:

```python
from openai import OpenAI
client = OpenAI(api_key=MODEL_API_KEY, base_url="https://api.meta.ai/v1")
r = client.responses.create(model="muse-spark-1.3", input="Your prompt here")
print(r.output_text)
```

Test every snippet once with your real key before marking a card verified.

## 6. Change E: Meta-aware planner (FR-4)

1. Meta cards that are verified and have mapped jobs enter the shortlist through the existing scoring; set `is_pick = true` on the main ones (Spark, Voice Transcribe, Image) so they rank well. Do not change scoring rules unless the smoke test shows a need.
2. Tool context passed to the synthesis prompt (`services/prompts.py`) gains `ecosystem`, `kind`, `model_id` for Meta cards.
3. Prompt rules to add: "Use only model IDs that appear in the tool context. Never invent a model ID. For a Meta model step, write the prompt to be sent to that model, with the expected output format."
4. The call snippet is not written by the model. The UI renders `api_snippet` from the card.
5. Post-check: after plan generation, scan step text for strings that look like Meta model IDs (`muse-` or `sam-` prefixes) and drop or flag any not present in the catalog.

## 7. Change F: smoke test (FR-2)

Script: `backend/scripts/smoke_plan.py`. Runs the planner on these goals with the real key and prints a pass/fail table:

1. I want a tool that turns my voice notes into structured orders. (must include a `transcribe_audio` step and a Meta card)
2. Build a landing page for my new product and deploy it.
3. I want to build a small app that stores customer records, with login.
4. Summarize 20 PDF reports and extract the key figures into a table.
5. Turn a screenshot of a design into a React component.
6. Make a set of promo images for my Instagram.
7. Add an AI assistant to my existing Node.js app using Meta's models. (must include a Meta card)
8. Transcribe a recorded interview and write a summary. (must include a `transcribe_audio` step)

Checks per plan: 1 to 6 steps; each step has a catalog tool and a non-empty prompt; no duplicate steps; no model ID outside the catalog. Also add a pytest that runs the same checks against a fake LLM so CI stays offline.

## 8. Change G: frontend (FR-3, FR-5)

Keep the current design and components. In `frontend/src/routes/tools.tsx`:

- Filter chip "Meta" (uses `?ecosystem=meta`) next to the existing filters.
- Meta badge and a kind label (Runnable, Open-weight, Developer tool, Platform) on cards.
- Detail view: model ID, capabilities (from jobs and input/output types), the `api_snippet` in a code block with a Copy button, sources, and the verified date.

In `frontend/src/routes/app.tsx` (step card): show the Meta badge and model ID; show the snippet in a collapsible block when the step's tool has one.

## 9. Change H: Run a text step (D4, stretch only)

Do this only if Changes A to G are done and tested.

- Endpoint: `POST /api/v1/workflows/{workflow_id}/steps/{step_id}/run`, body `{ "prompt": "optional edited prompt" }`.
- Rules: load the step from the database and check it belongs to the signed-in user; allow only if the step's tool is verified, `kind = runnable` and its `model_id` is a text model in the catalog; use the card's `model_id`, never a client-supplied one; max prompt length and output-token cap from config; 60-second timeout.
- Quota: reuse the existing quota service with a new daily counter (`RUN_STEPS_PER_DAY`, default 10). Count only successful runs.
- Storage: table `step_runs` (id, step_id, user_id, model_id, prompt, output_text, status, error_code, input_tokens, output_tokens, latency_ms, created_at). Additive migration.
- UI: Run button on eligible steps, output panel under the prompt, Copy and Download (.md). Show clear errors for quota, timeout and model unavailable.
- No streaming unless T1 proved streaming works and time remains.

## 10. Tests

- Unit: `llm` module with a mocked client (success, JSON repair retry, transient retry, timeout, unavailable model).
- Importer: new fields round-trip; unknown job slugs are dropped with a flag.
- Directory: `ecosystem=meta` filter returns only Meta cards.
- Planner: fake-LLM version of the smoke checks.
- Stretch: run endpoint ownership, quota, non-runnable rejection, saved output equals displayed output.
- All 134 existing tests keep passing.

## 11. Files touched (expected)

`core/config.py`, `.env.example`, `services/llm.py`, `services/interview.py`, `services/plan.py`, `services/prompts.py`, `services/importer.py`, `schemas/card_import.py`, `schemas/tool.py`, `models/tool.py`, `routers/tools.py`, `scripts/check_connections.py`, new migration, `data/meta_cards.json`, `scripts/smoke_plan.py`, tests, `frontend/src/routes/tools.tsx`, `frontend/src/routes/app.tsx`, README, `NEW_WORK.md`. Stretch: `routers/workflow.py` or a new run router, `models/step_run.py`, one more migration.
