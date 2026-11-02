import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowRight,
  Check,
  ChevronRight,
  Compass,
  Layers3,
  Menu,
  Sparkles,
  WandSparkles,
  X,
} from "lucide-react";
import { useState, useEffect } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { BrandMark } from "@/components/BrandMark";
import { ToolsDirectoryModal } from "@/components/ToolsDirectoryModal";
import { supabase } from "@/lib/supabase";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Pathwise — Turn your idea into a clear creation path" },
      {
        name: "description",
        content:
          "Pathwise recommends the right AI tools, prompts, and workflow to turn your idea into something real.",
      },
      { property: "og:title", content: "Pathwise — Your clear path from idea to launch" },
      {
        property: "og:description",
        content: "Find the right tools, prompts, and workflow for your next creative project.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const stages = [
  {
    name: "Draft",
    label: "Illustrative example · Step 1: Outline & structure",
    title: "Define the core foundation of your project",
    detail: "Distill user requirements, target audience, and key constraints into an actionable plan.",
    tool: "Claude",
    prompt: "Structure the initial brief and scope for this project...",
  },
  {
    name: "Build",
    label: "Illustrative example · Step 2: Core execution",
    title: "Implement the main components",
    detail: "Generate the necessary assets, models, or schema definitions to bring the idea to life.",
    tool: "Cursor",
    prompt: "Create the primary deliverables based on the draft requirements...",
  },
  {
    name: "Launch",
    label: "Illustrative example · Step 3: Polish & deploy",
    title: "Finalize details and prepare for release",
    detail: "Review, optimize, and publish the final result for your target audience.",
    tool: "Vercel",
    prompt: "Review the current state and deploy the production build...",
  },
];

const processSteps = [
  {
    number: "01",
    title: "Tell us",
    copy: "Describe what you want to make, who it is for, and what success looks like.",
  },
  {
    number: "02",
    title: "Get your path",
    copy: "Receive a focused sequence of verified tools, prompts, and decisions tailored to your goal.",
  },
  {
    number: "03",
    title: "Start creating",
    copy: "Move from one clear step to the next on the real tools without losing context.",
  },
];



function Header() {
  const [open, setOpen] = useState(false);
  const [session, setSession] = useState<any>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => setSession(session));
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/95 backdrop-blur-md" id="top">
      <div className="mx-auto flex h-[72px] max-w-[1440px] items-center justify-between px-5 sm:px-8 lg:px-12">
        <div className="flex items-center gap-8">
          <BrandMark />
          <nav className="hidden items-center gap-7 lg:flex" aria-label="Main navigation">
            <ToolsDirectoryModal />
            <a className="nav-link" href="#how-it-works">How it works</a>
            <a className="nav-link" href="#example">Example</a>
          </nav>
        </div>

        <div className="hidden items-center gap-3 lg:flex">
          {session ? (
            <Button asChild className="h-10 rounded-lg px-5 shadow-[var(--shadow-button)]">
              <Link to="/app">Go to Workspace</Link>
            </Button>
          ) : (
            <>
              <Button asChild variant="ghost" className="h-10 text-sm font-medium">
                <Link to="/login" search={{ mode: "signin" }}>Sign in</Link>
              </Button>
              <Button asChild className="h-10 rounded-lg px-5 shadow-[var(--shadow-button)]">
                <Link to="/login" search={{ mode: "signup" }}>Sign up</Link>
              </Button>
            </>
          )}
        </div>

        <div className="flex items-center gap-2 lg:hidden">
          <Button
            variant="ghost"
            size="icon"
            aria-label={open ? "Close navigation" : "Open navigation"}
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </Button>
        </div>
      </div>

      {open ? (
        <nav className="border-t border-border bg-background px-5 py-5 lg:hidden" aria-label="Mobile navigation">
          <div className="mx-auto grid max-w-[1440px] gap-2">
            <div className="py-1">
              <ToolsDirectoryModal />
            </div>
            <a href="#how-it-works" className="rounded-md px-3 py-2 text-sm font-medium hover:bg-muted" onClick={() => setOpen(false)}>
              How it works
            </a>
            <a href="#example" className="rounded-md px-3 py-2 text-sm font-medium hover:bg-muted" onClick={() => setOpen(false)}>
              Example
            </a>
            {session ? (
              <Button asChild className="mt-3 h-11 rounded-lg">
                <Link to="/app" onClick={() => setOpen(false)}>Go to Workspace</Link>
              </Button>
            ) : (
              <>
                <Link to="/login" search={{ mode: "signin" }} className="rounded-md px-3 py-2 text-sm font-medium hover:bg-muted" onClick={() => setOpen(false)}>
                  Sign in
                </Link>
                <Button asChild className="mt-2 h-11 rounded-lg">
                  <Link to="/login" search={{ mode: "signup" }} onClick={() => setOpen(false)}>Sign up</Link>
                </Button>
              </>
            )}
          </div>
        </nav>
      ) : null}
    </header>
  );
}

function WorkflowPreview({ compact = false }: { compact?: boolean }) {
  const [active, setActive] = useState(compact ? 1 : 0);
  const current = stages[active];

  if (!current) return null;

  return (
    <div className={cn("workflow-shell", compact && "workflow-shell-compact")}>
      <div className="flex items-center justify-between border-b border-border px-5 py-4 sm:px-7">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid size-8 shrink-0 place-items-center rounded-md bg-accent text-accent-foreground">
            <WandSparkles className="size-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">Web App MVP</p>
            <p className="text-xs text-muted-foreground">Illustrative example · 3 tailored steps (1–6 steps based on goal)</p>
          </div>
        </div>
        <span className="hidden items-center gap-1.5 text-xs font-medium text-emerald-600 sm:flex">
          <span className="size-1.5 rounded-full bg-emerald-500" /> Illustrative example
        </span>
      </div>

      <div className="grid min-h-[360px] md:grid-cols-[176px_minmax(0,1fr)]">
        <div className="border-b border-border bg-muted/45 p-3 md:border-r md:border-b-0 md:p-4">
          <div className="grid grid-cols-5 gap-1 md:grid-cols-1 md:gap-1.5" role="tablist" aria-label="Creation path stages">
            {stages.map((stage, index) => (
              <Button
                key={stage.name}
                type="button"
                role="tab"
                aria-selected={active === index}
                variant="ghost"
                onClick={() => setActive(index)}
                className={cn(
                  "h-auto min-w-0 justify-center rounded-md px-1.5 py-2 text-[11px] font-medium text-muted-foreground shadow-none md:justify-start md:px-3 md:py-2.5 md:text-sm",
                  active === index && "bg-card text-foreground shadow-[var(--shadow-soft)] hover:bg-card",
                )}
              >
                <span className={cn("hidden size-5 place-items-center rounded-full border text-[10px] md:grid", active === index && "border-primary bg-primary text-primary-foreground")}>
                  {index < active ? <Check className="size-3" /> : index + 1}
                </span>
                <span className="truncate">{stage.name}</span>
              </Button>
            ))}
          </div>
        </div>

        <div className="flex flex-col p-5 sm:p-7 lg:p-9" role="tabpanel">
          <p className="eyebrow">{current.label}</p>
          <h3 className="mt-4 max-w-lg text-2xl font-semibold leading-[1.18] sm:text-[32px]">{current.title}</h3>
          <p className="mt-4 max-w-lg text-sm leading-6 text-muted-foreground sm:text-[15px]">{current.detail}</p>
          <div className="mt-8 grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-border bg-background p-4">
              <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <Layers3 className="size-4 text-primary" /> Recommended tool
              </div>
              <p className="mt-3 text-sm font-semibold">{current.tool}</p>
            </div>
            <div className="rounded-lg border border-border bg-background p-4">
              <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <Sparkles className="size-4 text-primary" /> Starting prompt
              </div>
              <p className="mt-3 text-sm font-semibold leading-5">{current.prompt}</p>
            </div>
          </div>
          <div className="mt-auto flex items-center justify-between pt-8">
            <span className="text-xs text-muted-foreground">Step {active + 1} of {stages.length}</span>
            <Button
              variant="ghost"
              size="sm"
              className="text-primary hover:bg-accent"
              onClick={() => setActive((value) => (value + 1) % stages.length)}
            >
              Next step <ChevronRight />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Index() {
  return (
    <main className="min-h-screen overflow-hidden bg-background">
      <Header />

      {/* HERO SECTION */}
      <section className="mx-auto grid max-w-[1440px] items-center gap-12 px-5 pt-12 pb-16 sm:px-8 sm:pt-16 lg:min-h-[680px] lg:grid-cols-[0.78fr_1.22fr] lg:gap-14 lg:px-12 lg:pt-10 lg:pb-16 xl:gap-20">
        <div className="max-w-xl lg:pl-4">
          <p className="eyebrow">Your creation coach</p>
          <h1 className="mt-5 max-w-[580px] text-[44px] font-semibold leading-[0.98] sm:text-[64px] lg:text-[72px] tracking-tight">
            Turn your idea into a clear path.
          </h1>
          <p className="mt-6 max-w-[520px] text-[16px] leading-7 text-muted-foreground sm:text-lg">
            Tell Pathwise what you want to create. Get a tailored step-by-step path, verified tools from our database, and paste-ready prompts for each tool.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Button asChild size="lg" className="h-12 rounded-lg px-7 text-[15px] shadow-[var(--shadow-button)]">
              <Link to="/app">Start creating now <ArrowRight className="size-4" /></Link>
            </Button>
            <a
              href="#how-it-works"
              className="inline-flex h-12 items-center justify-center rounded-lg border border-border bg-background px-5 text-sm font-medium text-foreground hover:bg-muted"
            >
              How it works
            </a>
          </div>
        </div>
        <WorkflowPreview />
      </section>

      {/* VALUE PROP BANNER */}
      <section className="border-y border-border bg-card">
        <div className="mx-auto grid max-w-[1200px] gap-8 px-5 py-16 sm:px-8 md:grid-cols-[0.48fr_1fr] md:py-24 lg:px-12">
          <p className="eyebrow pt-2">Made for momentum</p>
          <p className="max-w-3xl text-[28px] font-medium leading-[1.25] sm:text-[38px] lg:text-[44px]">
            Less time comparing tools. More time making something that matters.
          </p>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how-it-works" className="mx-auto max-w-[1200px] px-5 py-20 sm:px-8 md:py-28 lg:px-12">
        <div className="grid gap-8 md:grid-cols-[0.48fr_1fr]">
          <div>
            <p className="eyebrow">How Pathwise works</p>
            <h2 className="mt-4 text-3xl font-semibold leading-tight sm:text-4xl">Clarity at every step.</h2>
          </div>
          <p className="max-w-xl text-base leading-7 text-muted-foreground md:pt-6">
            Pathwise is a coach, not a generator. You create on the real tool&apos;s own site. Pathwise interviews you, picks verified tools, and writes the prompt.
          </p>
        </div>
        <div className="mt-14 grid border-t border-border md:grid-cols-3">
          {processSteps.map((step, index) => (
            <article key={step.number} className={cn("py-8 md:min-h-[220px] md:px-8 md:py-9", index > 0 && "border-t border-border md:border-t-0 md:border-l")}>
              <span className="font-mono text-xs text-primary font-bold">{step.number}</span>
              <h3 className="mt-8 text-xl font-semibold">{step.title}</h3>
              <p className="mt-3 max-w-xs text-sm leading-6 text-muted-foreground">{step.copy}</p>
            </article>
          ))}
        </div>
      </section>

      {/* EXAMPLE SECTION */}
      <section id="example" className="bg-surface-strong py-20 md:py-28">
        <div className="mx-auto max-w-[1200px] px-5 sm:px-8 lg:px-12">
          <div className="grid items-end gap-8 md:grid-cols-[1fr_0.68fr]">
            <div>
              <p className="eyebrow">Example creation path</p>
              <h2 className="mt-4 max-w-2xl text-3xl font-semibold leading-tight sm:text-4xl">From a loose idea to a launch-ready plan.</h2>
            </div>
            <p className="max-w-md text-sm leading-6 text-muted-foreground md:justify-self-end">
              Explore each stage to see how Pathwise keeps the tool, prompt, and next decision in one clear view.
            </p>
          </div>
          <div className="mt-12 md:mt-16">
            <WorkflowPreview compact />
          </div>
        </div>
      </section>

      {/* GET STARTED CTA */}
      <section id="get-started" className="px-5 py-12 sm:px-8 sm:py-16">
        <div className="mx-auto flex max-w-[1344px] flex-col items-start justify-between gap-8 rounded-2xl bg-primary px-6 py-14 text-primary-foreground sm:px-10 md:flex-row md:items-end md:px-16 md:py-18 shadow-[var(--shadow-button)]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-primary-foreground/75">Your next idea deserves a path</p>
            <h2 className="mt-4 max-w-2xl text-3xl font-semibold leading-[1.1] sm:text-4xl md:text-5xl">Know what to do next.</h2>
          </div>
          <Button asChild variant="secondary" size="lg" className="h-12 shrink-0 rounded-lg bg-background px-7 text-foreground shadow-none hover:bg-background/90 font-semibold">
            <Link to="/app">Start creating <ArrowRight className="size-4" /></Link>
          </Button>
        </div>
      </section>

      {/* FOOTER */}
      <footer id="signin" className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-6 border-t border-border/60 px-5 py-8 sm:px-8 lg:px-12">
        <BrandMark />
        <div className="flex items-center gap-6 text-xs text-muted-foreground">
          <a href="#how-it-works" className="hover:text-foreground">How it works</a>
          <a href="#example" className="hover:text-foreground">Example</a>
          <Link to="/terms" className="hover:text-foreground">Terms</Link>
          <Link to="/privacy" className="hover:text-foreground">Privacy</Link>
          <Link to="/login" search={{ mode: "signin" }} className="hover:text-foreground">Sign in</Link>
          <Link to="/login" search={{ mode: "signup" }} className="text-primary font-medium hover:underline">Sign up</Link>
        </div>
        <p className="text-xs text-muted-foreground">© 2026 Pathwise AI. Real tools · Paste-ready prompts · Create with direction.</p>
      </footer>
    </main>
  );
}