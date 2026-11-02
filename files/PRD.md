# Pathwise AI: Hackathon Build PRD (v5)

Prepared Monday, Nov 2, 2026. Build window left: about two and a half days.
Submission deadline: Wed Nov 4, 9:00 PM ET (that is 3:00 AM Thu Nov 5 in Lagos). Plan to submit by about 3 PM ET Wed (9 PM Lagos).

This PRD replaces v4 for the hackathon. v4 is the longer-term vision; this document is what ships by Wednesday.

## 1. One line

Pathwise turns a goal into a tool-aware workflow. For builders it knows Meta's models: it picks the right Muse model, says why, and hands over a paste-ready prompt plus a call snippet.

## 2. Deliverables right now

| ID | Deliverable | Priority |
|---|---|---|
| D1 | A working workflow generator (interview, brief, plan, prompts) that runs entirely on the Meta Model API, with no Gemini | Must |
| D2 | A Meta AI model and tool directory inside the existing directory: filterable, with model IDs, capabilities, a "how to call" snippet, sources and verification status | Must |
| D3 | A Meta-aware planner: Meta cards appear in plans for the jobs they fit, and Meta steps carry the model ID and snippet | Must |
| D4 | Run button for Meta text steps (live call, saved output, download) | Stretch |
| D5 | Submission pack: public repo, README, `NEW_WORK.md`, 3-minute video | Must |

## 3. What is cut, and why

| Cut | Reason |
|---|---|
| Agentic loop, guided setup guides, skills system, artifacts and versioning | Not achievable in two days. Mention as roadmap in the README. |
| Manus front-end redesign | Too risky this late. Keep the current UI and add components. Manus stays a directory entry only if time allows. |
| Speech, image and segmentation runners | Directory cards only. No Run button for them. |
| 15 to 20 goal benchmark | Replaced by an 8-goal smoke test (see FR-2). |
| New learning features | Learn-as-you-build already exists in the repo (`why_step`, `why_tool`, `learn_note`). Leave it untouched. |

## 4. Demo goal

"I want a tool that turns my voice notes into structured orders."

Expected plan: transcribe the voice note (Muse Voice Transcribe), extract structured orders (Muse Spark, with structured output), build the interface (an external builder from the catalog), host it and add a database (existing catalog tools). Every Meta step shows the model ID and a call snippet. The directory page shows the Meta collection.

Test this exact goal until the output is stable. Keep a saved workflow as a fallback for the video.

## 5. Requirements and acceptance criteria

**FR-1 Meta provider (D1).**
All LLM calls go through one module that calls the Meta Model API with the OpenAI SDK (`base_url=https://api.meta.ai/v1`, default model `muse-spark-1.3`). No silent fallback to another model. Errors are sanitized. Acceptance: with `GEMINI_API_KEY` unset, interview, brief, plan and prompt generation work; the existing test suite passes.

**FR-2 Plan quality smoke test (D1).**
A script runs 8 fixed goals through the planner and checks: 1 to 6 steps; every step names a tool that exists in the catalog; every step has a non-empty prompt; steps are in a sensible order; no model ID appears that is not in the catalog. Acceptance: all 8 pass on the real API. Time-box prompt fixes to 60 minutes.

**FR-3 Meta directory (D2).**
At least 9 Meta cards (Muse Spark, Muse Wonder, Muse Voice Transcribe, SAM 3.1, Muse Image, Muse Spark Open, Muse Glimmer, Muse Code, Meta Model API). Each has: kind (runnable, open_weight, developer_tool, platform), model ID where one exists, a how-to-call snippet where one exists, sources, and a verification status. The directory has a Meta filter and badge, and the detail page shows model ID and snippet with a copy button. Acceptance: you have checked every card against dev.meta.ai and marked it verified in the admin console.

**FR-4 Meta-aware planner (D3).**
Verified Meta cards surface for the jobs they are mapped to. Steps that use a Meta model include its exact model ID and snippet. Acceptance: the demo goal produces a plan containing Muse Voice Transcribe and Muse Spark steps, and no invented model IDs.

**FR-5 Honest labels.**
Cards are labeled runnable, open-weight, developer tool or platform. A Run button appears only on steps whose tool is a text model and only if D4 shipped.

**FR-6 Run text step (D4, stretch).**
Endpoint runs the step's prompt on the card's model, with ownership check, daily quota, 60-second timeout and saved output with Copy and Download (.md). Acceptance: a Spark step runs from the browser and the saved output matches what is shown.

**FR-7 Submission (D5).**
Public repo; README (what it is, what is new, how to run, limits, tests); `NEW_WORK.md` listing what was built during the window; a 3-minute demo video; every team member listed; track confirmed.

## 6. Non-functional requirements

- Secrets only in environment variables. `.env` is git-ignored. Never in prompts, logs or the frontend.
- Additive database migrations only. No new auth system.
- Existing tests stay green; new behavior has tests.
- Keep existing quotas and rate limits.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Two and a half days is very short | Cut line in the playbook: drop D4 first, then trim frontend polish |
| Meta API access not yet confirmed for your account and region | Task T1 is a hello-world that proves it before any refactor |
| Structured output may behave differently than Gemini's | T1 tests it; the spec has a same-model fallback (JSON mode plus validation) |
| Planner output was poor in your earlier tests | FR-2 smoke test, time-boxed prompt fixes, pinned demo goal |
| Muse Code needs macOS, Linux or WSL | Run it on your Ubuntu laptop |
| Track and new-work rules | Confirm the track today; import commit plus `NEW_WORK.md` (playbook T0) |

## 8. Definition of done

- [ ] Interview to plan works on Meta only; tests green
- [ ] 8-goal smoke test passes
- [ ] 9 Meta cards verified by you, visible with filter and detail
- [ ] Demo goal produces the expected Meta-aware plan
- [ ] README, `NEW_WORK.md`, public repo, 3-minute video submitted before the deadline
