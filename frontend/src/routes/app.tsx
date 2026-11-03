import { useQuery } from "@tanstack/react-query";
import { createFileRoute, redirect, Link } from "@tanstack/react-router";
import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronRight,
  Code2,
  Compass,
  Copy,
  DollarSign,
  Download,
  ExternalLink,
  History,
  Layers3,
  Loader2,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Wand2,
  XCircle,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { AppHeader } from "@/components/AppHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  api,
  DailyLimitError,
  NotInBetaError,
  getApiBaseUrl,
  type AuthUserResponse,
  type InterviewAnswer,
  type InterviewQuestionResponse,
  type ProductBrief,
  type StepActionResponse,
  type StepRunResponse,
  type WorkflowResponse,
  type WorkflowStep,
} from "@/lib/api";
import { supabase } from "@/lib/supabase";

export const Route = createFileRoute("/app")({
  ssr: false,
  beforeLoad: async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) throw redirect({ to: "/login" });
  },
  head: () => ({
    meta: [
      { title: "Workspace — Pathwise" },
      { name: "description", content: "Describe your goal and get a step-by-step creation path." },
      { property: "og:title", content: "Workspace — Pathwise" },
      { property: "og:description", content: "Your Pathwise creation workspace." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  validateSearch: (search: Record<string, unknown>): { load?: number } => {
    const s = search as { load?: unknown };
    return s.load ? { load: Number(s.load) } : {};
  },
  component: AppPage,
});

const errMsg = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");

function AppPage() {
  const [sessionUser, setSessionUser] = useState<AuthUserResponse | null>(null);
  const [resendingEmail, setResendingEmail] = useState(false);
  const [goal, setGoal] = useState("");
  const [answers, setAnswers] = useState<InterviewAnswer[]>([]);
  const [question, setQuestion] = useState<InterviewQuestionResponse | null>(null);
  const [custom, setCustom] = useState("");
  const [brief, setBrief] = useState<ProductBrief | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [quotaLimitMessage, setQuotaLimitMessage] = useState<string | null>(null);

  useEffect(() => {
    api.getMe().then((me) => {
      setSessionUser(me);
    }).catch((e) => {
      console.error(e);
      window.location.href = "/login";
    });
  }, []);

  const { load } = Route.useSearch();

  useEffect(() => {
    if (load) {
      api.getWorkflow(load).then((wf) => {
        setGoal(wf.title || wf.brief.what_being_made || "");
        setBrief(wf.brief);
        setWorkflow(wf);
        setQuestion(null);
        setAnswers([]);
        toast.success(`Loaded path: "${wf.title || 'Untitled'}"`);
      }).catch((e) => {
        toast.error("Failed to load workflow");
        console.error(e);
      });
    }
  }, [load]);

  const { data: usageData } = useQuery({
    queryKey: ["usage"],
    queryFn: () => api.getUsage(),
    enabled: !!sessionUser,
  });

  const quota = usageData?.["workflow"];
  const isEmailVerified = sessionUser?.email_verified ?? true;

  async function handleResendEmail() {
    if (!sessionUser?.email) return;
    setResendingEmail(true);
    try {
      const { error: resendError } = await supabase.auth.resend({
        type: "signup",
        email: sessionUser.email,
      });
      if (resendError) throw resendError;
      toast.success("Verification email sent! Please check your inbox.");
    } catch (err: any) {
      toast.error(err?.message || "Failed to resend verification email.");
    } finally {
      setResendingEmail(false);
    }
  }

  async function turn(nextAnswers: InterviewAnswer[]) {
    setBusy("interview");
    setError("");
    try {
      const res = await api.submitInterview(goal, nextAnswers);
      setAnswers(nextAnswers);
      setCustom("");
      if (res.type === "question") {
        setQuestion(res);
      } else {
        setQuestion(null);
        setBrief(res.brief);
      }
    } catch (e: any) {
      if (e instanceof DailyLimitError) {
        const resetTime = new Date(e.details.resets_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const msg = `Daily limit reached for ${e.details.kind}. Resets at ${resetTime}.`;
        setError(msg);
        setQuotaLimitMessage(msg);
      } else if (e instanceof NotInBetaError) {
        setError("Pathwise is currently in private beta for invited creators. Your account does not have access yet. Please check back soon or request an invite.");
      } else {
        setError(errMsg(e));
      }
    } finally {
      setBusy(null);
    }
  }

  async function buildWorkflow() {
    if (!brief) return;
    setBusy("workflow");
    setError("");
    try {
      const result = await api.generateWorkflow(brief);
      setWorkflow(result);
      toast.success("Creation path generated successfully!");
    } catch (e: any) {
      if (e instanceof DailyLimitError) {
        const resetTime = new Date(e.details.resets_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const msg = `Daily limit reached for ${e.details.kind}. Resets at ${resetTime}.`;
        setError(msg);
        setQuotaLimitMessage(msg);
      } else if (e instanceof NotInBetaError) {
        setError("Pathwise is currently in private beta for invited creators. Your account does not have access yet. Please check back soon or request an invite.");
      } else {
        setError(errMsg(e));
      }
    } finally {
      setBusy(null);
    }
  }

  async function stepAction(
    step: WorkflowStep,
    action: "regenerate" | "switch_tool" | "finished" | "recheck",
    payload?: string,
    feedbackResult?: "worked" | "partly" | "didnt"
  ) {
    if (!workflow) return;
    setBusy(`${step.step_id}:${action}`);
    setError("");
    try {
      let res: StepActionResponse;
      if (action === "recheck") {
        res = await api.recheckStep(workflow.id, step.step_id);
      } else {
        res = await api.updateStep({
          workflow_id: workflow.id,
          step_id: step.step_id,
          step,
          action,
          ...(payload !== undefined ? { payload } : {}),
          ...(feedbackResult ? { feedback_result: feedbackResult } : {}),
          brief: workflow.brief,
          steps: workflow.steps,
        });
      }
      setWorkflow((w) => {
        if (!w) return w;
        let steps = w.steps.map((s) => (s.step_id === step.step_id ? res.step : s));
        if (res.next_step) {
          steps = steps.map((s) => (s.step_id === res.next_step!.step_id ? res.next_step! : s));
        }
        return { ...w, steps };
      });
      if (res.message) toast.success(res.message);
    } catch (e: any) {
      if (e instanceof DailyLimitError) {
        const resetTime = new Date(e.details.resets_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const msg = `Daily limit reached. Resets at ${resetTime}.`;
        setError(msg);
        toast.error(msg);
      } else {
        setError(errMsg(e));
        toast.error(errMsg(e));
      }
    } finally {
      setBusy(null);
    }
  }

  function reset() {
    setGoal("");
    setAnswers([]);
    setQuestion(null);
    setBrief(null);
    setWorkflow(null);
    setError("");
  }

  const started = question || brief || answers.length > 0;

  if (!sessionUser)
    return (
      <div
        role="status"
        aria-label="Loading workspace"
        className="grid min-h-screen place-items-center bg-background"
      >
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
    );

  return (
    <div className="min-h-screen bg-background">
      <AppHeader session={{ email: sessionUser.email, role: sessionUser.role }} />
      <main className="mx-auto max-w-[960px] px-5 py-12 sm:px-8">
        {/* Verification banner if unverified */}
        {!isEmailVerified ? (
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-900 dark:text-amber-200">
            <div className="flex items-center gap-2">
              <AlertTriangle className="size-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <span>Please verify your email address to access generation and step tools.</span>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={resendingEmail}
              onClick={handleResendEmail}
              className="h-8 text-xs border-amber-500/40 hover:bg-amber-500/20"
            >
              {resendingEmail ? <Loader2 className="size-3 animate-spin mr-1.5" /> : null}
              Resend verification email
            </Button>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="eyebrow">Interactive Studio</p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              asChild
              className="text-xs gap-1.5"
            >
              <Link to="/app/history">
                <History className="size-3.5" />
                History
              </Link>
            </Button>
            {started ? (
              <Button variant="ghost" size="sm" onClick={reset} className="text-xs text-muted-foreground gap-1.5">
                <RotateCcw className="size-3.5" /> Start new path
              </Button>
            ) : null}
          </div>
        </div>

        {quota ? (
          <div className="mt-4 flex items-center justify-between rounded-lg border border-primary/20 bg-primary/5 px-4 py-2.5 text-sm">
            <div className="text-muted-foreground">
              <span className="font-medium text-foreground">{Math.max(0, quota.limit - quota.used)}</span> of {quota.limit} paths left today
            </div>
            {quota.limit - quota.used <= 0 ? (
              <div className="text-xs text-muted-foreground">
                Resets at {new Date(quota.resets_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            ) : null}
          </div>
        ) : null}

        <h1 className="mt-4 text-3xl sm:text-4xl font-semibold tracking-tight">
          What do you want to create?
        </h1>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Describe what you want to make, who it is for, and what success looks
          like.
        </p>

        {!started ? (
          <form
            className="mt-8 grid gap-4"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              if (goal.trim()) turn([]);
            }}
          >
            <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
              <Textarea
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="e.g. A weekly newsletter for independent designers, or a micro-SaaS landing page with auth"
                className="min-h-32 bg-background text-base resize-none border-border"
              />
              <div className="mt-4 flex items-center justify-between flex-wrap gap-3">
                <p className="text-xs text-muted-foreground">
                  Be as broad or detailed as you like. Pathwise will ask 1–5 clarifying questions.
                </p>
                <Button
                  type="submit"
                  size="lg"
                  disabled={
                    !goal.trim() ||
                    busy !== null ||
                    !isEmailVerified ||
                    (quota && quota.limit - quota.used <= 0) ||
                    !!quotaLimitMessage
                  }
                  className="px-6"
                >
                  {busy === "interview" ? (
                    <Loader2 className="size-4 animate-spin mr-2" />
                  ) : (
                    <Sparkles className="size-4 mr-2" />
                  )}
                  Continue
                </Button>
              </div>
            </div>
          </form>
        ) : (
          <div className="mt-4 rounded-xl border border-border bg-muted/30 p-4 flex items-center justify-between">
            <div className="flex items-center gap-2.5 min-w-0">
              <Compass className="size-4 text-primary shrink-0" />
              <span className="text-sm font-medium text-foreground truncate">{goal}</span>
            </div>
            <button className="text-xs text-primary hover:underline shrink-0 ml-4" onClick={reset}>
              Start over
            </button>
          </div>
        )}

        {error ? (
          <div role="alert" className="mt-6 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        {/* QUESTION SKELETON (first question still generating) */}
        {!question && !brief && busy === "interview" ? (
          <section
            aria-label="Loading next question"
            className="mt-10 rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8"
          >
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-16" />
            </div>
            <Skeleton className="mt-4 h-7 w-3/4" />
            <div className="mt-6 grid gap-2.5">
              <Skeleton className="h-[52px] w-full rounded-lg" />
              <Skeleton className="h-[52px] w-full rounded-lg" />
              <Skeleton className="h-[52px] w-full rounded-lg" />
            </div>
          </section>
        ) : null}

        {/* INTERVIEW QUESTION STEP */}
        {question ? (
          <section className="mt-10 rounded-2xl border border-border bg-card p-6 sm:p-8 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                Question {answers.length + 1} of 5 max
              </span>
              <span className="text-xs text-muted-foreground">Step {answers.length + 1}</span>
            </div>
            <h2 className="mt-3 text-xl sm:text-2xl font-semibold leading-snug">{question.question}</h2>

            <div className="mt-6 grid gap-2.5">
              {question.options.map((opt) => (
                <Button
                  key={opt}
                  variant="outline"
                  className="h-auto justify-start whitespace-normal py-3.5 px-4 text-left font-normal hover:border-primary/50 hover:bg-primary/5"
                  disabled={busy !== null}
                  onClick={() => turn([...answers, { question: question.question, answer: opt }])}
                >
                  <ChevronRight className="size-4 mr-2 shrink-0 text-muted-foreground" />
                  <span>{opt}</span>
                </Button>
              ))}
            </div>

            {question.allow_custom_text ? (
              <form
                className="mt-4 flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (custom.trim()) turn([...answers, { question: question.question, answer: custom.trim() }]);
                }}
              >
                <Input
                  value={custom}
                  onChange={(e) => setCustom(e.target.value)}
                  placeholder="Or write your own specific answer..."
                  className="bg-background"
                />
                <Button type="submit" disabled={!custom.trim() || busy !== null}>
                  Send
                </Button>
              </form>
            ) : null}

            {busy === "interview" ? (
              <div
                role="status"
                aria-label="Thinking about your answer"
                className="mt-6 flex items-center gap-1.5"
              >
                <span className="size-2 animate-bounce rounded-full bg-primary/70 [animation-delay:-0.3s]" />
                <span className="size-2 animate-bounce rounded-full bg-primary/70 [animation-delay:-0.15s]" />
                <span className="size-2 animate-bounce rounded-full bg-primary/70" />
              </div>
            ) : null}
          </section>
        ) : null}

        {/* PRODUCT BRIEF CARD */}
        {brief && !workflow ? (
          <section className="mt-10 rounded-2xl border border-border bg-card p-6 sm:p-8 shadow-sm">
            <p className="eyebrow">Product Brief Finalized</p>
            <h2 className="mt-2 text-2xl font-semibold">{brief.what_being_made}</h2>
            <dl className="mt-6 grid gap-6 text-sm sm:grid-cols-2">
              {brief.product_name ? (
                <BriefItem label="Product Name" value={brief.product_name} />
              ) : null}
              <BriefItem label="Purpose" value={brief.purpose} />
              <BriefItem label="Target Audience" value={brief.target_audience} />
              <BriefItem label="Must Haves" list={brief.must_haves} />
              <BriefItem label="Nice To Haves" list={brief.nice_to_haves} />
              <BriefItem label="Constraints" list={brief.constraints} />
              <BriefItem label="Assumptions" list={brief.assumptions} />
            </dl>
            <div className="mt-8 border-t border-border pt-6">
              <Button
                size="lg"
                className="px-8 shadow-md"
                onClick={buildWorkflow}
                disabled={busy !== null || !isEmailVerified}
              >
                {busy === "workflow" ? (
                  <Loader2 className="size-4 animate-spin mr-2" />
                ) : (
                  <Wand2 className="size-4 mr-2" />
                )}
                Build My Creation Path
              </Button>
            </div>
          </section>
        ) : null}

        {/* WORKFLOW STEPS */}
        {workflow ? (
          <section className="mt-10 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="eyebrow">Verified Workflow Path</p>
                <h2 className="mt-1 text-2xl font-bold">{workflow.steps.length} Sequenced Action Steps</h2>
              </div>
            </div>

            {/* COST SUMMARY (Catalog v3, Slice C5) */}
            {workflow.cost_summary ? (
              <div className="rounded-2xl border border-border bg-card p-5 shadow-xs space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <DollarSign className="size-4 text-primary" />
                    <h3 className="text-sm font-bold text-foreground">Estimated Workflow Cost</h3>
                  </div>
                  {workflow.cost_summary.mode === "free" ? (
                    <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 gap-1 text-xs font-semibold py-1">
                      <CheckCircle2 className="size-3.5" />
                      <span>
                        {workflow.cost_summary.pricing_complete === false
                          ? "Estimated Free · verify pricing"
                          : "100% Free Plan ($0/mo)"}
                      </span>
                    </Badge>
                  ) : (
                    <Badge className="bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30 gap-1 text-xs font-semibold py-1">
                      <AlertCircle className="size-3.5" />
                      <span>
                        May Incur Costs{workflow.cost_summary.estimated_monthly_usd ? ` (~$${workflow.cost_summary.estimated_monthly_usd}/mo)` : ""}
                      </span>
                    </Badge>
                  )}
                </div>

                {workflow.cost_summary.notes && workflow.cost_summary.notes.length > 0 && (
                  <ul className="text-xs text-muted-foreground space-y-1 list-disc pl-4 pt-1">
                    {workflow.cost_summary.notes.map((note, idx) => (
                      <li key={idx} className="leading-relaxed">{note}</li>
                    ))}
                  </ul>
                )}
              </div>
            ) : null}

            <ol className="grid gap-6">
              {workflow.steps.map((step) => (
                <StepCard
                  key={step.step_id}
                  step={step}
                  workflowId={workflow.id}
                  busy={busy}
                  onAction={stepAction}
                />
              ))}
            </ol>
          </section>
        ) : null}
      </main>
    </div>
  );
}

function BriefItem({ label, value, list }: { label: string; value?: string; list?: string[] }) {
  if (!value && !list?.length) return null;
  return (
    <div className="rounded-lg border border-border/60 bg-muted/20 p-3.5">
      <dt className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="mt-1.5 leading-6 text-foreground text-sm">
        {value ?? (
          <ul className="list-disc pl-4 space-y-1">
            {list!.map((i) => (
              <li key={i}>{i}</li>
            ))}
          </ul>
        )}
      </dd>
    </div>
  );
}

function StepCard({
  step,
  workflowId,
  busy,
  onAction,
}: {
  step: WorkflowStep;
  workflowId: number;
  busy: string | null;
  onAction: (
    s: WorkflowStep,
    a: "regenerate" | "switch_tool" | "finished" | "recheck",
    p?: string,
    f?: "worked" | "partly" | "didnt"
  ) => void;
}) {
  const [note, setNote] = useState("");
  const [feedbackResult, setFeedbackResult] = useState<"worked" | "partly" | "didnt">("worked");
  const [openingLink, setOpeningLink] = useState(false);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<StepRunResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const b = (a: string) => busy === `${step.step_id}:${a}`;

  async function handleOpenTool() {
    if (!step.primary_tool) return;
    setOpeningLink(true);
    try {
      const { go_url } = await api.openLink(workflowId, step.step_id, step.primary_tool.id);
      const targetUrl = go_url.startsWith("http") ? go_url : `${getApiBaseUrl()}${go_url}`;
      window.open(targetUrl, "_blank", "noopener,noreferrer");
    } catch (err: any) {
      toast.error(err?.message || "Failed to open tool link.");
    } finally {
      setOpeningLink(false);
    }
  }

  async function handleRunStep() {
    setRunning(true);
    setRunError(null);
    try {
      const result = await api.runStep(workflowId, step.step_id);
      setRunResult(result);
    } catch (err: any) {
      const message = err?.message || "The run failed. Please try again.";
      setRunError(message);
      toast.error(message);
    } finally {
      setRunning(false);
    }
  }

  function handleCopyOutput() {
    if (!runResult?.output_text) return;
    navigator.clipboard.writeText(runResult.output_text);
    toast.success("Output copied.");
  }

  function handleDownloadOutput() {
    if (!runResult?.output_text) return;
    const blob = new Blob(
      [
        `# Step ${step.step_number} output\n\nModel: ${runResult.model_id}\n\n${runResult.output_text}\n`,
      ],
      { type: "text/markdown" },
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `step-${step.step_number}-output.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  // Calm card for kind="no_tool" or steps with no verified tool
  if (step.kind === "no_tool" || !step.primary_tool) {
    return (
      <li className="rounded-2xl border border-dashed border-border/80 bg-muted/20 p-6 sm:p-7 transition-all">
        <div className="flex items-center justify-between gap-4">
          <span className="font-mono text-xs font-bold px-2.5 py-1 rounded-md bg-muted text-muted-foreground">
            STEP {String(step.step_number).padStart(2, "0")}
          </span>
          <span className="text-xs font-medium text-amber-600 dark:text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded">
            No tool verified yet
          </span>
        </div>

        <h3 className="mt-3 text-xl font-semibold text-foreground">{step.job}</h3>
        {step.why_step ? (
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{step.why_step}</p>
        ) : null}

        <div className="mt-5 rounded-xl border border-border/60 bg-background/60 p-4">
          <p className="text-sm text-muted-foreground">
            No verified tool yet. Come back later.
          </p>
          <div className="mt-3">
            <Button
              size="sm"
              variant="outline"
              className="text-xs h-8 gap-1.5"
              disabled={busy !== null}
              onClick={() => onAction(step, "recheck")}
            >
              {b("recheck") ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
              Check again
            </Button>
          </div>
        </div>
      </li>
    );
  }

  // Standard verified tool card
  return (
    <li className="rounded-2xl border border-border bg-card p-6 sm:p-7 shadow-sm transition-all hover:shadow-md">
      <div className="flex items-center justify-between gap-4">
        <span className="font-mono text-xs font-bold px-2.5 py-1 rounded-md bg-primary/10 text-primary">
          STEP {String(step.step_number).padStart(2, "0")}
        </span>
        <span className="text-xs font-medium text-muted-foreground">{step.primary_tool.category}</span>
      </div>

      <h3 className="mt-3 text-xl font-semibold text-foreground">{step.job}</h3>
      {step.why_step ? (
        <p className="mt-1 text-xs text-muted-foreground">{step.why_step}</p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          {step.primary_tool.logo_url ? (
            <img
              src={step.primary_tool.logo_url}
              alt=""
              className="size-5 rounded object-contain"
            />
          ) : (
            <Layers3 className="size-4 text-primary" />
          )}
          <span className="text-sm font-semibold">{step.primary_tool.name}</span>
          {step.primary_tool.is_pick && (
            <Badge className="bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30 gap-1 text-[10px] py-0.5">
              <Sparkles className="size-2.5 text-amber-500 fill-amber-500" />
              <span>Pick</span>
            </Badge>
          )}
          <span className="text-xs rounded bg-muted px-2 py-0.5 text-muted-foreground font-medium capitalize">
            {step.primary_tool.pricing_model || step.primary_tool.pricing}
          </span>
          {step.primary_tool.ecosystem === "meta" && (
            <Badge className="bg-sky-500/15 text-sky-700 dark:text-sky-300 border-sky-500/30 gap-1 text-[10px] py-0.5">
              <span>Meta</span>
            </Badge>
          )}
          {step.primary_tool.model_id && (
            <span className="text-[11px] font-mono rounded bg-muted px-2 py-0.5 text-muted-foreground">
              {step.primary_tool.model_id}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={openingLink}
            onClick={handleOpenTool}
            className="h-8 gap-1.5 text-xs"
          >
            {openingLink ? <Loader2 className="size-3.5 animate-spin" /> : null}
            Open tool <ExternalLink className="size-3.5" />
          </Button>
        </div>
      </div>

      {step.primary_tool.why_chosen ? (
        <p className="mt-2 text-xs text-muted-foreground">{step.primary_tool.why_chosen}</p>
      ) : null}

      {/* FREE TIER NOTE (Catalog v3, Slice C5) */}
      {step.free_tier_note ? (
        <div className="mt-3 rounded-xl bg-muted/40 border border-border/60 p-3 text-xs text-foreground/90 flex items-start gap-2.5">
          <DollarSign className="size-3.5 text-emerald-500 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-muted-foreground text-[10px] uppercase block mb-0.5">
              Free Tier & Limits:
            </span>
            <span className="leading-relaxed">{step.free_tier_note}</span>
          </div>
        </div>
      ) : null}

      {/* STEP WARNINGS (Catalog v3, Slice C5) */}
      {step.warnings && step.warnings.length > 0 ? (
        <div className="mt-2 space-y-1">
          {step.warnings.map((w, idx) => (
            <div
              key={idx}
              className="rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 text-xs text-amber-800 dark:text-amber-300 flex items-center gap-1.5"
            >
              <AlertTriangle className="size-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      ) : null}

      {/* PROMPT OR SETUP STEPS */}
      {step.content_type === "steps" &&
      step.action_steps &&
      step.action_steps.length > 0 ? (
        <div className="mt-5 rounded-xl border border-border bg-background p-4 sm:p-5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-primary uppercase tracking-wider flex items-center gap-1.5">
              <Layers3 className="size-3.5" /> Setup Steps
            </span>
            <Button
              size="sm"
              variant="secondary"
              className="h-7 px-2.5 text-xs gap-1.5 font-medium"
              onClick={() => {
                navigator.clipboard.writeText((step.action_steps || []).join("\n"));
                toast.success("Steps copied to clipboard!");
              }}
            >
              <Copy className="size-3.5" /> Copy
            </Button>
          </div>
          <ol className="mt-3 space-y-2">
            {step.action_steps.map((action, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-sm leading-relaxed text-foreground/90"
              >
                <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
                  {i + 1}
                </span>
                <span className="whitespace-pre-wrap">{action}</span>
              </li>
            ))}
          </ol>
        </div>
      ) : step.prompt ? (
        <div className="mt-5 rounded-xl border border-border bg-background p-4 sm:p-5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-primary uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="size-3.5" /> Paste-Ready Prompt {step.technique ? `(${step.technique})` : ""}
            </span>
            <Button
              size="sm"
              variant="secondary"
              className="h-7 px-2.5 text-xs gap-1.5 font-medium"
              onClick={() => {
                navigator.clipboard.writeText(step.prompt || "");
                toast.success("Prompt copied to clipboard!");
              }}
            >
              <Copy className="size-3.5" /> Copy
            </Button>
          </div>
          <pre className="mt-3 whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground/90 bg-muted/20 p-3 rounded-lg border border-border/50 select-all">
            {step.prompt}
          </pre>
        </div>
      ) : null}

      {/* META API SNIPPET */}
      {step.primary_tool.api_snippet ? (
        <Collapsible className="mt-4 rounded-xl border border-border bg-background">
          <CollapsibleTrigger className="group flex w-full items-center justify-between gap-2 p-4 text-xs font-semibold text-primary uppercase tracking-wider">
            <span className="flex items-center gap-1.5">
              <Code2 className="size-3.5" /> API snippet
            </span>
            <ChevronRight className="size-3.5 transition-transform group-data-[state=open]:rotate-90" />
          </CollapsibleTrigger>
          <CollapsibleContent className="px-4 pb-4">
            <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-foreground/90 bg-muted/20 p-3 rounded-lg border border-border/50 overflow-x-auto max-h-48 overflow-y-auto">
              {step.primary_tool.api_snippet}
            </pre>
            <Button
              size="sm"
              variant="secondary"
              className="mt-2 h-7 px-2.5 text-xs gap-1.5 font-medium"
              onClick={() => {
                navigator.clipboard.writeText(
                  step.primary_tool?.api_snippet || "",
                );
                toast.success("Snippet copied to clipboard!");
              }}
            >
              <Copy className="size-3.5" /> Copy snippet
            </Button>
          </CollapsibleContent>
        </Collapsible>
      ) : null}

      {/* EXPECTED OUTPUT & HANDOFF */}
      <div className="mt-4 space-y-1.5 text-xs sm:text-sm">
        {step.output_expected ? (
          <p className="text-foreground">
            <span className="font-semibold text-muted-foreground">Expected Output:</span> {step.output_expected}
          </p>
        ) : null}
        {step.handoff_note ? (
          <p className="text-muted-foreground bg-accent/40 rounded-md p-2 border border-border/50">
            <span className="font-semibold text-foreground">Handoff Note:</span> {step.handoff_note}
          </p>
        ) : null}
      </div>

      {/* ALTERNATIVES & REGENERATE */}
      <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border pt-4">
        <Button
          size="sm"
          variant="outline"
          className="text-xs h-8 gap-1.5"
          disabled={busy !== null}
          onClick={() => onAction(step, "regenerate")}
        >
          {b("regenerate") ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
          {step.content_type === "steps" ? "Regenerate Steps" : "Regenerate Prompt"}
        </Button>
        {step.can_run ? (
          <Button
            size="sm"
            variant="default"
            className="text-xs h-8 gap-1.5"
            disabled={busy !== null || running}
            onClick={handleRunStep}
          >
            {running ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Play className="size-3.5" />
            )}
            {running ? "Running..." : "Run"}
          </Button>
        ) : null}
        {step.alternatives?.map((alt) => (
          <Button
            key={alt.id}
            size="sm"
            variant="ghost"
            className="text-xs h-8 text-muted-foreground hover:text-foreground"
            disabled={busy !== null}
            onClick={() => onAction(step, "switch_tool", String(alt.id))}
          >
            Switch to {alt.name}
          </Button>
        ))}
      </div>

      {/* LIVE RUN OUTPUT (T9) */}
      {runResult ? (
        <div className="mt-4 rounded-lg border border-border bg-muted/30 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold">
              Live output{" "}
              <span className="font-mono font-normal text-muted-foreground">
                · {runResult.model_id}
              </span>
            </p>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="ghost"
                className="h-7 gap-1 text-xs"
                onClick={handleCopyOutput}
              >
                <Copy className="size-3.5" /> Copy
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 gap-1 text-xs"
                onClick={handleDownloadOutput}
              >
                <Download className="size-3.5" /> .md
              </Button>
            </div>
          </div>
          <p className="mt-3 max-h-96 overflow-y-auto whitespace-pre-wrap text-sm leading-6">
            {runResult.output_text}
          </p>
          <p className="mt-2 font-mono text-[10px] text-muted-foreground">
            {runResult.input_tokens + runResult.output_tokens} tokens ·{" "}
            {runResult.latency_ms} ms
          </p>
        </div>
      ) : null}
      {runError && !runResult ? (
        <p className="mt-3 text-xs text-destructive">{runError}</p>
      ) : null}

      {/* FINISHED STEP / USAGE SIGNALS (Catalog v3, Slice C7) */}
      {step.status === "done" ? (
        <div className="mt-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-3 text-xs text-emerald-800 dark:text-emerald-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" />
            <span className="font-semibold">Step Finished</span>
            {step.handoff_note ? (
              <span className="text-muted-foreground ml-2">Note: {step.handoff_note}</span>
            ) : null}
          </div>
          <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-semibold">
            Done
          </span>
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-border bg-muted/20 p-4 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span className="text-xs font-semibold text-foreground">
              Did this step work?
            </span>
            <div className="flex items-center gap-1.5">
              <Button
                type="button"
                size="sm"
                variant={feedbackResult === "worked" ? "default" : "outline"}
                className={`h-7 px-2.5 text-xs gap-1 ${feedbackResult === "worked" ? "bg-emerald-600 hover:bg-emerald-700 text-white" : "hover:text-emerald-600"}`}
                onClick={() => setFeedbackResult("worked")}
              >
                <Check className="size-3" /> Worked
              </Button>
              <Button
                type="button"
                size="sm"
                variant={feedbackResult === "partly" ? "default" : "outline"}
                className={`h-7 px-2.5 text-xs gap-1 ${feedbackResult === "partly" ? "bg-amber-600 hover:bg-amber-700 text-white" : "hover:text-amber-600"}`}
                onClick={() => setFeedbackResult("partly")}
              >
                <AlertCircle className="size-3" /> Partly
              </Button>
              <Button
                type="button"
                size="sm"
                variant={feedbackResult === "didnt" ? "default" : "outline"}
                className={`h-7 px-2.5 text-xs gap-1 ${feedbackResult === "didnt" ? "bg-rose-600 hover:bg-rose-700 text-white" : "hover:text-rose-600"}`}
                onClick={() => setFeedbackResult("didnt")}
              >
                <XCircle className="size-3" /> Didn't
              </Button>
            </div>
          </div>

          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              onAction(step, "finished", note.trim() || undefined, feedbackResult);
            }}
          >
            <Input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="What did you create or decide? (Passes context to next step)"
              className="h-8 text-xs bg-background"
            />
            <Button
              type="submit"
              size="sm"
              variant="default"
              className="h-8 text-xs px-3 gap-1.5 shrink-0"
              disabled={busy !== null}
            >
              {b("finished") ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
              Mark Finished
            </Button>
          </form>
        </div>
      )}
    </li>
  );
}
