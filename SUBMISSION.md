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
- Public GitHub repo URL: https://github.com/okizman09/PathwiseAI ([confirm it is PUBLIC])
- 3-minute demo video URL: [YOU] (YouTube; must open logged out)
- Most Viral X post link: [YOU, only if competing for that track]
- How likely to build with / recommend Meta Model API, overall opinion,
  recommend Muse Code, model-choice criteria, switching friction, production
  blockers: [YOU — your genuine ratings; don't let anyone else fill these]
- Consent checkbox: [YOU]

## Submitted video (tutoring goal, recorded Nov 5)

- 0:00–0:25 — Problem: goal known, models/tools/order unknown.
- 0:25–0:50 — What Pathwise is: planner + verified directory, Meta-powered.
- 0:50–1:15 — Goal "landing page for my home tutoring service in Lagos, with
  the copy written for me"; follow-ups; 2-step workflow appears.
- 1:15–2:00 — Live Run of Step 1 (Muse Spark drafts the copy); JSON renders.
- 2:00–2:20 — Proof cut: finished Lovable page + leads table (steps 2–3
  completed offline exactly as written).
- 2:20–2:50 — Why not ChatGPT: verified tools, structured steps, live runs.
- 2:50–3:00 — Close. (Voice-note/transcribe goal retired: its headline step
  can't run live; Muse Voice Transcribe stays listed in the directory.)

## Checks before you submit

Run in PowerShell (git is blocked for the sandbox; these are yours):

```powershell
git ls-files | Select-String "\.env$|\.db$|\.mp4$|\.mov$"  # must print NOTHING
git status --short                              # review, then stage by name
git add .gitignore NEW_WORK.md SUBMISSION.md backend/app/services/plan.py backend/tests/test_plan_checks.py frontend/src/routes/app.tsx frontend/src/lib/api.ts
git commit -m "Submission hardening: Run reliability, overflow fix, tracker + pack"
git push origin main                            # then confirm the repo is PUBLIC
```

- [ ] Demo goal produces a good plan 3 times in a row (fresh run each time)
- [ ] Judge demo account created (verified email); credentials go in the submission notes, never in the repo; sign-up works without an invite
- [ ] Billing alert set in the Meta dashboard (global run cap is 200/day in code)
- [ ] Live Run returns real output (not empty) on the structure step
- [ ] Video recorded, uploaded, opens in an incognito window
- [ ] All members listed; track + problem statement selected
- [ ] Meta API credits claimed; old GitHub token revoked
- [ ] Submitted before Wed 3 PM ET (hard deadline 9 PM ET)
