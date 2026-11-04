# Submission pack — paste-ready answers + checklists

Fields marked [YOU] need answers only you can give. Everything else is drafted
from the code and verified this session — no claims beyond what is built.

## Form answers (ready to paste)

### Project Description
Pathwise AI turns a build idea into a clear step-by-step creation path. It
interviews you about your goal, locks a concrete product brief, picks verified
tools from a curated catalog, and generates a sequenced plan with paste-ready
prompts (or guided setup steps for deploy/database work). Prompt steps on
Meta's text models run live inside the app with persisted output. It solves
the "blank page" problem for creators: knowing the goal but not which models
and tools to use, in what order, with what words.

### Describe your use of Meta products to build the submitted project
Meta Model API (`muse-spark-1.3` at `api.meta.ai/v1`) is the sole LLM provider:
product interviews, workflow decomposition, prompt synthesis, step actions, and
live step runs all call it with strict `json_schema` structured output
(low reasoning effort on the creation path after latency probing). The catalog
holds 9 verified Meta cards (Muse Spark/Wonder, Voice Transcribe, Image,
SAM 3.1, Muse Code, Model API, Spark Open, Glimmer) with facts checked against
official Meta sources, and Muse Spark + Muse Wonder are executable live-run
targets with their model IDs shown in the UI.

### Why are Meta's models important to your solution?
One provider covers the whole loop: the same model family interviews the user,
plans the workflow, writes the prompts, and executes them live. Strict-schema
JSON keeps every step machine-validated, and the range (text, code, voice,
image) lets the planner match jobs to models instead of generic assistants.
Without Meta's models there is no interview, no plan, and no Run button.

### Feedback on partner technologies (Fireworks, Modal, Baseten)
We did not use Fireworks, Modal, or Baseten on this build — all inference went
through the Meta Model API, so we have no comparative feedback to give.

### Biggest obstacle
Hidden reasoning tokens consuming output budgets: early calls returned empty
text with the full budget spent on reasoning. Fixed with generous per-call
budgets, an opt-in low reasoning effort (probed: ~34% faster, identical
output), and treating empty output as a refunded failure. Second: Supabase
pooler dropping connections during long model calls — fixed with checkout
health checks.

## Fields only you can answer

- Team Name: [YOU]
- Track: [YOU]
- Problem statement: [YOU]
- Public GitHub repo URL: [YOU] (must be public; see checks below)
- 3-minute demo video URL: [YOU] (YouTube; must open logged out)
- Most Viral X post link: [YOU, only if competing for that track]
- How likely to build with / recommend Meta Model API, overall opinion,
  recommend Muse Code, model-choice criteria, switching friction, production
  blockers: [YOU — your genuine ratings; don't let anyone else fill these]
- Consent checkbox: [YOU]

## Demo script (3 minutes, T9 shipped)

- 0:00–0:20 — Problem: people know the goal, not the models/tools/order.
- 0:20–0:50 — Enter "I want a tool that turns my voice notes into structured
  orders"; interview + brief run on Meta (say so).
- 0:50–1:50 — The workflow: transcribe step (Muse Voice Transcribe + model ID),
  structure step (Muse Spark + prompt + call snippet), build/hosting steps.
- 1:50–2:20 — Live Run of the structure step; JSON output renders in-app.
- 2:20–2:40 — Meta directory: filter, a card, sources, verified badge.
- 2:40–2:55 — What was built this week (point at NEW_WORK.md).
- 2:55–3:00 — Close: roadmap is Run for more models, verified agent steps.

## Checks before you submit

Run in PowerShell (git is blocked for the sandbox; these are yours):

```powershell
git ls-files | Select-String "\.env$|\.db$"     # must print NOTHING
git status --short                              # review, then stage by name
git add README.md NEW_WORK.md SUBMISSION.md render.yaml docs/DEPLOY.md backend/.env.example backend/ frontend/
git commit -m "T10: submission pack (README, Meta deploy files, Run + hardening)"
git push origin main                            # then confirm the repo is PUBLIC
```

- [ ] Demo goal produces a good plan 3 times in a row (freshrun each time)
- [ ] Live Run returns real output (not empty) on the structure step
- [ ] Video recorded, uploaded, opens in an incognito window
- [ ] All members listed; track + problem statement selected
- [ ] Meta API credits claimed; old GitHub token revoked
- [ ] Submitted before Wed 3 PM ET (hard deadline 9 PM ET)
