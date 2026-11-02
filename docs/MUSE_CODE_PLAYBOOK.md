# Muse Code Playbook: building Pathwise for the hackathon

Today is Monday, Nov 2. Deadline: Wed Nov 4, 9:00 PM ET (3:00 AM Thu in Lagos). Aim to submit by 3 PM ET Wednesday (9 PM Lagos), and stop building by noon ET (6 PM Lagos).

Read `PRD.md` and `SPEC.md` first. Every prompt below tells Muse Code to read the relevant part of `docs/SPEC.md`, so the prompts stay short.

## Part A: Set up (about 30 minutes)

**Where to run it.** Meta's workshop handbook says Muse Code runs on macOS or Linux, and on Windows only through WSL. Use your Ubuntu laptop. If your repo is on the Windows machine, push it to GitHub and clone it on Ubuntu.

**Install.** Follow Meta's page exactly: https://dev.meta.ai/docs/muse-code (I have not read that page, so I can't give you the commands). If the install fails and costs you more than 30 minutes, switch to OpenCode with the Meta provider config from earlier in our chat. The prompts below work in either tool.

**Sign in.** Start `muse` from the project root. In the workshop, the first run asked how to sign in; choose "Paste an API key" and use your Meta Model API key. Say yes if it asks whether to trust the folder.

**Two keys, two places.** Muse Code uses your key to work with you. Your app uses `MODEL_API_KEY` in `backend/.env`. Neither goes in a prompt, a commit or a screenshot.

**Revoke the GitHub token** you pasted earlier in our chat: GitHub, Settings, Developer settings, Personal access tokens.

## Part B: Working rules

1. One task per prompt. Wait for the report, then check it.
2. Commit after every task that passes: `git add -A && git commit -m "T3: migrate call sites to Meta LLM module"`.
3. You run the tests yourself and read the result. Do not take "all tests pass" on trust.
4. If Muse Code edits things you did not ask for, press Esc, then undo with `git checkout -- <paths>`.
5. When a task fails twice, stop, paste the error to me, and move on if it is not on the critical path.

## Part C: Ground-rules prompt (send this first, every new Muse Code session)

```text
You are my coding assistant on Pathwise AI, an existing FastAPI + React project. This first message only sets ground rules: do not create, edit or delete any file until I ask. Reply "Ready" and wait.

Ground rules:
* Build only what I ask, then stop and report. Write the smallest readable change that does the job.
* Inspect the existing code before editing. Follow the project's existing conventions and keep working behaviour intact.
* Read docs/PRD.md and docs/SPEC.md when I point you to them. If the spec names a file or function that does not exist, tell me instead of guessing.
* Use additive database migrations only. Do not change the taxonomy file. Do not add a new auth system.
* Never open .env, and never print, log or commit API keys or populated environment values.
* Do not run any script that calls the Meta API unless I ask. You may run the offline test suite when a task says to.
* Every completion report lists: files changed, commands you ran and their results, and any limitation or doubt.
```

## Part D: Task prompts

Times are estimates. If you are behind, use the cut line in Part E.

### T0: Repo, provenance, track (manual, 20 minutes)

```bash
# 1. New repo with an honest starting point
cp -r Pathwise-AI pathwise-hackathon && cd pathwise-hackathon && rm -rf .git
git init && git add -A
git ls-files | grep -E '\.env$|\.db$|\.sqlite' || echo "no env/db files tracked"   # must print the 'no env/db' line
git commit -m "chore: import pre-hackathon Pathwise (unchanged)"

# 2. Add the three documents from this pack into docs/, plus backend/data/meta_cards.json
git add -A && git commit -m "docs: hackathon PRD, spec, playbook and Meta seed cards"

# 3. Create a PUBLIC GitHub repo and push
```

Create `NEW_WORK.md` with this starting content, and add a line to it after every task:

```markdown
# New work during the hackathon (Oct 26 to Nov 4, 2026)

The first commit, "import pre-hackathon Pathwise (unchanged)", is the code that existed before the event.
Everything in later commits was built during the hackathon.

## Built during the event
- (add one line per task: what, and the commit)

## Reused from before the event
- Auth, quotas, catalog and importer, planner scoring, existing UI (see the first commit)
```

Then confirm your track on the submit page: https://cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit. If you are on Indie, ask in #questions on Discord whether extending an existing project is allowed, or switch to Startup. Get it settled today.

### T1: Meta hello-world and decision gate (30 minutes)

```text
Read docs/SPEC.md section 2. Create backend/scripts/meta_hello.py, a standalone script that reads MODEL_API_KEY from the environment (never from a literal) and uses the OpenAI Python SDK with base_url https://api.meta.ai/v1. It must:
1. List models (client.models.list()) and print whether "muse-spark-1.3" is in the list.
2. Make a plain text call with the Responses API and print the output text.
3. Try structured output with text={"format": {"type": "json_schema", "name": "Order", "schema": <a small Pydantic schema's JSON schema>, "strict": True}}. If that errors, try text={"format": {"type": "json_object"}} with the schema described in the instructions, and validate with Pydantic. Print which method worked.
4. Make one streaming call (stream=True) and print the event types it receives, then the final text.
5. Print a short summary table: models ok, text ok, structured method, streaming ok. Print only error type and status code on failure, never the key or full responses.
Add openai to backend/requirements.txt. Do not run the script. Report files changed.
```

Run it yourself: `cd backend && MODEL_API_KEY=... python scripts/meta_hello.py`.

**Decision gate.** If models or text fail with 401, 403 or a region message, stop and see Part F. Everything else depends on this passing. Paste the summary table to me.

### T2: New LLM module (60 to 90 minutes)

```text
Read docs/SPEC.md section 2 and the current backend/app/services/llm.py and backend/app/core/config.py.
Add the Meta implementation to services/llm.py next to the existing Gemini code (do not delete the Gemini code yet and do not touch any call site): generate_structured and generate_text as specified, using AsyncOpenAI against settings.META_BASE_URL with settings.MODEL_API_KEY and settings.META_MODEL. Use the structured-output method that T1 proved works: <PASTE THE METHOD FROM THE T1 TABLE HERE>. Keep the same-model, two-attempt retry rule. Map provider errors to the existing sanitized error types in core/errors.py; never log keys, prompts or raw provider errors.
Add the settings MODEL_API_KEY, META_BASE_URL, META_MODEL, LLM_TIMEOUT_SECONDS to core/config.py and .env.example (keep the Gemini settings for now). Update scripts/check_connections.py to check the Meta models endpoint.
Add unit tests with a mocked client: success, JSON repair retry, transient retry then success, timeout, unavailable model. Run the offline test suite and report the result. Report files changed.
```

Run the tests yourself, then commit.

### T3: Migrate every call site (60 to 90 minutes)

```text
Read docs/SPEC.md section 3. Find every use of the Gemini helpers with: grep -rIl "generate_content_resilient\|get_gemini_client\|GEMINI" backend
Migrate services/interview.py, services/plan.py, services/prompts.py and the tool-card extraction in services/llm.py and services/research/extractor.py to generate_structured / generate_text. Keep prompt wording and behaviour the same; change only the call mechanics. Update the tests that patch the old functions (tests/conftest.py, tests/test_beta_readiness.py and any other) to patch the new ones.
When nothing references Gemini any more, delete the Gemini client code, the GEMINI_* settings and the google-genai dependency from requirements. Run the offline test suite and report the result. Report files changed and anything you could not migrate.
```

Then run a real end-to-end test yourself: start the backend with your key and take one goal through interview, brief and plan in the UI or by API. Commit.

### T4: Catalog fields for Meta (45 minutes)

```text
Read docs/SPEC.md section 4. Add an Alembic migration (additive, nullable) adding ecosystem, kind, model_id and api_snippet to the tools table, following the style of the existing migrations. Update models/tool.py, schemas/tool.py (base, read and admin schemas), schemas/card_import.py (optional ecosystem, kind, model_id, api_snippet and docs_url) and services/importer.py (map these fields on both create and update). Add an optional "ecosystem" query filter to the public tools list endpoint in routers/tools.py. Add tests: new fields round-trip through the importer, and ecosystem=meta returns only Meta tools. Run the offline test suite and report the result. Report files changed.
```

Apply the migration to your local database yourself (`alembic upgrade head`). Commit.

### T5: Import the Meta cards and verify them (45 minutes, mostly you)

```text
Read docs/SPEC.md section 5. Run: cd backend && python -m app.scripts.import_cards data/meta_cards.json against the local SQLite database. Report the created/updated/rejected counts and every flag the importer raised, per card. Do not edit data/meta_cards.json. If a card is rejected, explain why and propose a minimal fix to the importer or the card, and wait for me.
```

Then do this yourself for every card. It is the part that makes the directory trustworthy.

1. Open the card's official page (the URL on the card) and the models page: https://dev.meta.ai/docs/models.
2. Check the model ID, the summary and each pro and con. Fix anything the page does not support.
3. Fill the snippets that are empty (Voice Transcribe, SAM 3.1, Muse Image) by copying the official example. Run each snippet once with your key.
4. Check Meta's pricing page and fill `pricing_model` if you can; otherwise leave it as unknown.
5. In the admin console, mark the card Verified. The planner only uses verified cards.

Commit the corrected seed file and log it in `NEW_WORK.md`.

### T6: Meta-aware planner (45 minutes)

```text
Read docs/SPEC.md section 6 and backend/app/services/prompts.py, plan.py and planner/scoring.py. Implement: (1) pass ecosystem, kind and model_id to the synthesis prompt's tool context for Meta tools; (2) add the prompt rules: use only model IDs present in the tool context, never invent one, and for a Meta model step write the prompt to be sent to that model with the expected output format; (3) after plan generation, scan step text for strings starting with "muse-" or "sam-" and flag or remove any that are not model_ids in the catalog; (4) do not change the scoring rules. Do not make the model write the API snippet; the UI renders it from the card. Add tests with a fake LLM covering the invented-ID check and the tool-context fields. Run the offline test suite and report the result. Report files changed.
```

Then set `is_pick` on Muse Spark, Muse Voice Transcribe and Muse Image in the admin console. Commit.

### T7: Smoke test and quality fixes (60 minutes, time-boxed)

```text
Read docs/SPEC.md section 7. Create backend/scripts/smoke_plan.py that runs the planner on the 8 goals listed there with the real API and prints a pass/fail table using the checks listed. Also add a pytest that applies the same checks to a fake LLM. Do not run the script against the real API. Report files changed.
```

Run it yourself. Paste the failures to me, and I will suggest the smallest prompt fixes. Apply them with Muse Code one at a time, and stop after 60 minutes even if one goal still fails. A plan that fails on a goal you will not demo is acceptable; the demo goal (goal 1) must pass.

### T8: Frontend (60 to 90 minutes)

```text
Read docs/SPEC.md section 8 and the existing frontend/src/routes/tools.tsx and app.tsx, and how the app currently calls the API. Keep the current design, components and styling. Implement: (1) a "Meta" filter chip on the tools page using the ecosystem query parameter; (2) a Meta badge and a kind label (Runnable, Open-weight, Developer tool, Platform) on tool cards; (3) in the tool detail view, show model ID, the api_snippet in a code block with a Copy button, sources and the verified date; (4) in the step card, show the Meta badge and model ID, and a collapsible snippet when the step's tool has one. Do not add new dependencies. Run the type check, the linter and the build, and report the results. Report files changed.
```

Check it in the browser yourself on a phone-width window and a desktop one. Commit.

### T9: Run a text step (stretch: only if T1 to T8 are done before noon ET Tuesday)

```text
Read docs/SPEC.md section 9. Implement the run endpoint, the step_runs table (additive migration), the quota counter, ownership checks, and the Run button, output panel, Copy and Download (.md) in the step card for eligible steps only. Use the model_id from the verified catalog card, never from the request. Add tests for ownership, quota, rejection of non-runnable steps, and that the saved output equals what is returned. Run the offline test suite and report the result. Report files changed.
```

If you are not ahead of schedule, skip T9 and say in the README that live Run is on the roadmap.

### T10: README and submission files (45 minutes)

```text
Update README.md with: what Pathwise is, what is new for the hackathon (Meta provider, Meta directory, Meta-aware planner), how to run it locally (backend and frontend), the environment variables, the tests, and honest limitations. Add a roadmap section listing: live Run for more models, guided setup steps, an agent loop with verification, and a skills system. Update NEW_WORK.md so every task from T1 onward has a line. Do not add claims that are not in the code. Report files changed.
```

## Part E: Schedule and cut line (Lagos time in brackets)

| When | Do |
|---|---|
| Mon Nov 2 evening | T0, T1, T2. If you have energy, T3. |
| Tue Nov 3 morning | T3 (if not done), T4, T5 |
| Tue Nov 3 afternoon | T6, T7 |
| Tue Nov 3 evening | T8 |
| Wed Nov 4 until noon ET (6 PM) | Finish T8, deploy, rehearse the demo three times. T9 only if everything above is green. |
| Wed Nov 4 noon to 3 PM ET (6 to 9 PM) | T10, record the video, submit |

**Cut line.** If T3 is not done by Tuesday noon, stop everything else: nothing works without it. If T8 is not done by Wednesday noon ET, ship the Meta filter and badge only. Always cut T9 first.

## Part F: Troubleshooting

| Symptom | What to do |
|---|---|
| 401 or 403 on the first call | Wrong key, or the key lacks access to the model. Check the key in the Meta dashboard and that credits are claimed with a card on file. |
| Model not found or region message | Read the Geographic Use Policy at https://dev.meta.ai/legal/geographic-use-policy. Ask in #questions on Discord, and tell them your region and model. |
| 429 | The SDK already retries; slow down and retry in a minute. |
| `json_schema` rejected | Use the `json_object` method from T1 and validate with Pydantic. |
| Tests fail after T3 | Almost always a mock still pointing at an old function; ask Muse Code to list tests that patch old names. |
| Migration fails on Postgres but not SQLite | Check column types and defaults; run `alembic upgrade head` against a copy first. |
| Muse Code edits files you did not name | Esc, `git checkout -- <paths>`, and resend the task with "change only these files". |
| Streaming does not work | Skip it. Nothing in the P0 scope needs streaming. |

## Part G: Demo script (3 minutes)

| Time | Show |
|---|---|
| 0:00 to 0:20 | The problem: people know the goal, not which models and tools to use or in what order |
| 0:20 to 0:50 | Enter "I want a tool that turns my voice notes into structured orders"; the interview and brief run on Meta (say so) |
| 0:50 to 1:50 | The workflow: transcribe step shows Muse Voice Transcribe with its model ID; extraction step shows Muse Spark with the prompt and the call snippet; the build and hosting steps use catalog tools |
| 1:50 to 2:30 | The Meta directory: filter, a card, its sources and verified date |
| 2:30 to 2:50 | What was built this week (point at `NEW_WORK.md`) |
| 2:50 to 3:00 | Close: roadmap is Run, guided setup and verified agent steps |

If T9 shipped, add a live Run of the extraction step at 1:50 and move the directory to 2:20.

## Part H: Submission checklist

- [ ] Track confirmed on the submit page
- [ ] Repo is public and `git ls-files` shows no `.env` or database files
- [ ] README, `NEW_WORK.md` and the first import commit are in place
- [ ] Every Meta card is verified and its snippet tested
- [ ] Demo goal produces the expected plan three times in a row
- [ ] 3-minute video uploaded; link opens when logged out
- [ ] Every team member is listed on the submission
- [ ] Submitted before 3 PM ET Wednesday, well ahead of the 9 PM ET deadline
- [ ] Meta API credits claimed (deadline Wed 9 PM ET) and the old GitHub token revoked
