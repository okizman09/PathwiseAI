import { useQuery } from "@tanstack/react-query";
import {
  createFileRoute,
  redirect,
  Link,
  useNavigate,
} from "@tanstack/react-router";
import {
  AlertTriangle,
  Compass,
  History,
  Loader2,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { AppHeader } from "@/components/AppHeader";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  BriefPanel,
  InterviewPanel,
  WorkflowView,
  type StepActionKind,
  type StepFeedbackResult,
} from "@/components/workspace";
import {
  api,
  DailyLimitError,
  NotInBetaError,
  type AuthUserResponse,
  type InterviewAnswer,
  type InterviewQuestionResponse,
  type ProductBrief,
  type StepActionResponse,
  type WorkflowResponse,
  type WorkflowStep,
} from "@/lib/api";
import { supabase } from "@/lib/supabase";

export const Route = createFileRoute("/app")({
  ssr: false,
  beforeLoad: async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session) throw redirect({ to: "/login" });
  },
  head: () => ({
    meta: [
      { title: "Workspace — Pathwise" },
      {
        name: "description",
        content: "Describe your goal and get a step-by-step creation path.",
      },
      { property: "og:title", content: "Workspace — Pathwise" },
      {
        property: "og:description",
        content: "Your Pathwise creation workspace.",
      },
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

const errMsg = (e: unknown) =>
  e instanceof Error ? e.message : "Something went wrong.";

const APP_STATE_KEY = "pathwise:app-state:v1";

type AppSnapshot = {
  goal: string;
  answers: InterviewAnswer[];
  question: InterviewQuestionResponse | null;
  custom: string;
  brief: ProductBrief | null;
  workflowId: number | null;
};

function readSnapshot(): AppSnapshot | null {
  try {
    const raw = localStorage.getItem(APP_STATE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AppSnapshot>;
    if (typeof parsed !== "object" || parsed === null) return null;
    return {
      goal: typeof parsed.goal === "string" ? parsed.goal : "",
      answers: Array.isArray(parsed.answers) ? parsed.answers : [],
      question: parsed.question ?? null,
      custom: typeof parsed.custom === "string" ? parsed.custom : "",
      brief: parsed.brief ?? null,
      workflowId:
        typeof parsed.workflowId === "number" ? parsed.workflowId : null,
    };
  } catch {
    return null;
  }
}

function writeSnapshot(snap: AppSnapshot) {
  try {
    localStorage.setItem(APP_STATE_KEY, JSON.stringify(snap));
  } catch {
    // Storage full or unavailable: the workspace still works, a refresh just won't restore.
  }
}

function clearSnapshot() {
  try {
    localStorage.removeItem(APP_STATE_KEY);
  } catch {
    // ignore
  }
}

function AppPage() {
  const [sessionUser, setSessionUser] = useState<AuthUserResponse | null>(null);
  const [resendingEmail, setResendingEmail] = useState(false);
  const [goal, setGoal] = useState("");
  const [answers, setAnswers] = useState<InterviewAnswer[]>([]);
  const [question, setQuestion] = useState<InterviewQuestionResponse | null>(
    null,
  );
  const [custom, setCustom] = useState("");
  const [brief, setBrief] = useState<ProductBrief | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [quotaLimitMessage, setQuotaLimitMessage] = useState<string | null>(
    null,
  );
  const [meFailed, setMeFailed] = useState(false);
  const [meAttempt, setMeAttempt] = useState(0);
  const navigate = useNavigate({ from: Route.id });
  const loadedRef = useRef<number | null>(null);
  const restoredRef = useRef(false);

  useEffect(() => {
    setMeFailed(false);
    api
      .getMe()
      .then((me) => {
        setSessionUser(me);
      })
      .catch(async (e) => {
        console.error(e);
        // Stay on the page for transient failures; only leave when truly logged out.
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session) {
          window.location.href = "/login";
          return;
        }
        setMeFailed(true);
      });
  }, [meAttempt]);

  const { load } = Route.useSearch();

  // Explicit ?load= (history links, shared URLs, back/forward): fetch it.
  useEffect(() => {
    if (!load || loadedRef.current === load) return;
    loadedRef.current = load;
    api
      .getWorkflow(load)
      .then((wf) => {
        setGoal(wf.title || wf.brief.what_being_made || "");
        setBrief(wf.brief);
        setWorkflow(wf);
        setQuestion(null);
        setAnswers([]);
        toast.success(`Loaded path: "${wf.title || "Untitled"}"`);
      })
      .catch((e) => {
        toast.error("Failed to load workflow");
        console.error(e);
      });
  }, [load]);

  // Plain refresh with no ?load=: restore the last snapshot once.
  useEffect(() => {
    if (restoredRef.current || load) return;
    restoredRef.current = true;
    const snap = readSnapshot();
    if (!snap) return;
    setGoal(snap.goal);
    setAnswers(snap.answers);
    setQuestion(snap.question);
    setCustom(snap.custom);
    setBrief(snap.brief);
    if (snap.workflowId) {
      loadedRef.current = snap.workflowId;
      api
        .getWorkflow(snap.workflowId)
        .then((wf) => {
          setWorkflow(wf);
        })
        .catch((e) => {
          console.error(e);
        });
    }
  }, [load]);

  // Capture every state change so a refresh restores exactly this view.
  useEffect(() => {
    writeSnapshot({
      goal,
      answers,
      question,
      custom,
      brief,
      workflowId: workflow?.id ?? readSnapshot()?.workflowId ?? null,
    });
  }, [goal, answers, question, custom, brief, workflow]);

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
    } catch (err: unknown) {
      toast.error(
        err instanceof Error && err.message
          ? err.message
          : "Failed to resend verification email.",
      );
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
    } catch (e: unknown) {
      if (e instanceof DailyLimitError) {
        const resetTime = new Date(e.details.resets_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
        const msg = `Daily limit reached for ${e.details.kind}. Resets at ${resetTime}.`;
        setError(msg);
        setQuotaLimitMessage(msg);
      } else if (e instanceof NotInBetaError) {
        setError(
          "Pathwise is currently in private beta for invited creators. Your account does not have access yet. Please check back soon or request an invite.",
        );
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
      loadedRef.current = result.id;
      navigate({ search: { load: result.id }, replace: true });
      toast.success("Creation path generated successfully!");
    } catch (e: unknown) {
      if (e instanceof DailyLimitError) {
        const resetTime = new Date(e.details.resets_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
        const msg = `Daily limit reached for ${e.details.kind}. Resets at ${resetTime}.`;
        setError(msg);
        setQuotaLimitMessage(msg);
      } else if (e instanceof NotInBetaError) {
        setError(
          "Pathwise is currently in private beta for invited creators. Your account does not have access yet. Please check back soon or request an invite.",
        );
      } else {
        setError(errMsg(e));
      }
    } finally {
      setBusy(null);
    }
  }

  async function stepAction(
    step: WorkflowStep,
    action: StepActionKind,
    payload?: string,
    feedbackResult?: StepFeedbackResult,
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
        let steps = w.steps.map((s) =>
          s.step_id === step.step_id ? res.step : s,
        );
        if (res.next_step) {
          steps = steps.map((s) =>
            s.step_id === res.next_step!.step_id ? res.next_step! : s,
          );
        }
        return { ...w, steps };
      });
      if (res.message) toast.success(res.message);
    } catch (e: unknown) {
      if (e instanceof DailyLimitError) {
        const resetTime = new Date(e.details.resets_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
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
    setCustom("");
    setBrief(null);
    setWorkflow(null);
    setError("");
    loadedRef.current = null;
    clearSnapshot();
    navigate({ search: {}, replace: true });
  }

  const started = question || brief || answers.length > 0;

  if (!sessionUser) {
    if (meFailed) {
      return (
        <div className="grid min-h-screen place-items-center bg-background px-5">
          <div className="max-w-sm text-center">
            <p className="text-sm font-semibold">
              Couldn&apos;t load your workspace
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Check your connection and try again — your work is saved on this
              device.
            </p>
            <Button className="mt-4" onClick={() => setMeAttempt((n) => n + 1)}>
              Retry
            </Button>
          </div>
        </div>
      );
    }
    return (
      <div
        role="status"
        aria-label="Loading workspace"
        className="grid min-h-screen place-items-center bg-background"
      >
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <AppHeader
        session={{ email: sessionUser.email, role: sessionUser.role }}
      />
      <main className="mx-auto max-w-[960px] px-5 py-12 sm:px-8">
        {/* Verification banner if unverified */}
        {!isEmailVerified ? (
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-900 dark:text-amber-200">
            <div className="flex items-center gap-2">
              <AlertTriangle className="size-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <span>
                Please verify your email address to access generation and step
                tools.
              </span>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={resendingEmail}
              onClick={handleResendEmail}
              className="h-8 text-xs border-amber-500/40 hover:bg-amber-500/20"
            >
              {resendingEmail ? (
                <Loader2 className="size-3 animate-spin mr-1.5" />
              ) : null}
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
              <Button
                variant="ghost"
                size="sm"
                onClick={reset}
                className="text-xs text-muted-foreground gap-1.5"
              >
                <RotateCcw className="size-3.5" /> Start new path
              </Button>
            ) : null}
          </div>
        </div>

        {quota ? (
          <div className="mt-4 flex items-center justify-between rounded-lg border border-primary/20 bg-primary/5 px-4 py-2.5 text-sm">
            <div className="text-muted-foreground">
              <span className="font-medium text-foreground">
                {Math.max(0, quota.limit - quota.used)}
              </span>{" "}
              of {quota.limit} paths left today
            </div>
            {quota.limit - quota.used <= 0 ? (
              <div className="text-xs text-muted-foreground">
                Resets at{" "}
                {new Date(quota.resets_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
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
                  Be as broad or detailed as you like. Pathwise will ask 1–5
                  clarifying questions.
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
              <span className="text-sm font-medium text-foreground truncate">
                {goal}
              </span>
            </div>
            <button
              className="text-xs text-primary hover:underline shrink-0 ml-4"
              onClick={reset}
            >
              Start over
            </button>
          </div>
        )}

        {error ? (
          <div
            role="alert"
            className="mt-6 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
          >
            {error}
          </div>
        ) : null}

        <InterviewPanel
          question={question}
          answers={answers}
          busy={busy}
          custom={custom}
          showSkeleton={!question && !brief && busy === "interview"}
          onCustomChange={setCustom}
          onAnswer={turn}
        />

        {brief && !workflow ? (
          <BriefPanel
            brief={brief}
            busy={busy}
            isEmailVerified={isEmailVerified}
            onBuild={buildWorkflow}
          />
        ) : null}

        {workflow ? (
          <WorkflowView workflow={workflow} busy={busy} onAction={stepAction} />
        ) : null}
      </main>
    </div>
  );
}
