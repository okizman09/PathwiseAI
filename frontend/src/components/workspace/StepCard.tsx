import { useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";
import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronRight,
  Code2,
  Copy,
  DollarSign,
  Download,
  ExternalLink,
  Layers3,
  Loader2,
  Play,
  RefreshCw,
  Sparkles,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import {
  api,
  getApiBaseUrl,
  type StepRunResponse,
  type WorkflowStep,
} from "@/lib/api";
import { FEATURE_LIVE_RUN, FEATURE_META_SHOWCASE } from "@/lib/features";
import type { StepActionHandler } from "./types";

function highlightJson(json: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re =
    /("(?:[^"\\]|\\.)*")(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;
  let last = 0;
  let k = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(json)) !== null) {
    if (m.index > last)
      parts.push(<span key={k++}>{json.slice(last, m.index)}</span>);
    const tok = m[0];
    const cls = m[1]
      ? m[2]
        ? "text-sky-700 dark:text-sky-300 font-medium"
        : "text-emerald-700 dark:text-emerald-300"
      : "text-amber-600 dark:text-amber-400";
    parts.push(
      <span key={k++} className={cls}>
        {tok}
      </span>,
    );
    last = m.index + tok.length;
  }
  if (last < json.length) parts.push(<span key={k++}>{json.slice(last)}</span>);
  return parts;
}

export function StepCard({
  step,
  workflowId,
  busy,
  onAction,
}: {
  step: WorkflowStep;
  workflowId: number;
  busy: string | null;
  onAction: StepActionHandler;
}) {
  const [note, setNote] = useState("");
  const [feedbackResult, setFeedbackResult] = useState<
    "worked" | "partly" | "didnt"
  >("worked");
  const [openingLink, setOpeningLink] = useState(false);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<StepRunResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const outputPretty = useMemo(() => {
    if (!runResult?.output_text) return null;
    try {
      const parsed = JSON.parse(runResult.output_text) as unknown;
      return { kind: "json" as const, text: JSON.stringify(parsed, null, 2) };
    } catch {
      return { kind: "text" as const, text: runResult.output_text };
    }
  }, [runResult]);
  const b = (a: string) => busy === `${step.step_id}:${a}`;

  async function handleOpenTool() {
    if (!step.primary_tool) return;
    setOpeningLink(true);
    try {
      const { go_url } = await api.openLink(
        workflowId,
        step.step_id,
        step.primary_tool.id,
      );
      const targetUrl = go_url.startsWith("http")
        ? go_url
        : `${getApiBaseUrl()}${go_url}`;
      window.open(targetUrl, "_blank", "noopener,noreferrer");
    } catch (err: unknown) {
      toast.error(
        err instanceof Error && err.message
          ? err.message
          : "Failed to open tool link.",
      );
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
    } catch (err: unknown) {
      const message =
        err instanceof Error && err.message
          ? err.message
          : "The run failed. Please try again.";
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

        <h3 className="mt-3 text-xl font-semibold text-foreground">
          {step.job}
        </h3>
        {step.why_step ? (
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
            {step.why_step}
          </p>
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
              {b("recheck") ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <RefreshCw className="size-3.5" />
              )}
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
        <span className="text-xs font-medium text-muted-foreground">
          {step.primary_tool.category}
        </span>
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
          <span className="text-sm font-semibold">
            {step.primary_tool.name}
          </span>
          {step.primary_tool.is_pick && (
            <Badge className="bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30 gap-1 text-[10px] py-0.5">
              <Sparkles className="size-2.5 text-amber-500 fill-amber-500" />
              <span>Pick</span>
            </Badge>
          )}
          <span className="text-xs rounded bg-muted px-2 py-0.5 text-muted-foreground font-medium capitalize">
            {step.primary_tool.pricing_model || step.primary_tool.pricing}
          </span>
          {FEATURE_META_SHOWCASE && step.primary_tool.ecosystem === "meta" && (
            <Badge className="bg-sky-500/15 text-sky-700 dark:text-sky-300 border-sky-500/30 gap-1 text-[10px] py-0.5">
              <span>Meta</span>
            </Badge>
          )}
          {FEATURE_META_SHOWCASE && step.primary_tool.model_id && (
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
        <p className="mt-2 text-xs text-muted-foreground">
          {step.primary_tool.why_chosen}
        </p>
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
                navigator.clipboard.writeText(
                  (step.action_steps || []).join("\n"),
                );
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
              <Sparkles className="size-3.5" /> Paste-Ready Prompt{" "}
              {step.technique ? `(${step.technique})` : ""}
            </span>
            <div className="flex items-center gap-2">
              {FEATURE_LIVE_RUN && step.can_run ? (
                <Button
                  size="sm"
                  variant="default"
                  className="h-7 px-2.5 text-xs gap-1.5 font-medium"
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
          </div>
          <pre className="mt-3 whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground/90 bg-muted/20 p-3 rounded-lg border border-border/50 select-all">
            {step.prompt}
          </pre>
        </div>
      ) : null}

      {/* META API SNIPPET */}
      {FEATURE_META_SHOWCASE && step.primary_tool.api_snippet ? (
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
            <span className="font-semibold text-muted-foreground">
              Expected Output:
            </span>{" "}
            {step.output_expected}
          </p>
        ) : null}
        {step.handoff_note ? (
          <p className="text-muted-foreground bg-accent/40 rounded-md p-2 border border-border/50">
            <span className="font-semibold text-foreground">Handoff Note:</span>{" "}
            {step.handoff_note}
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
          {b("regenerate") ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <RefreshCw className="size-3.5" />
          )}
          {step.content_type === "steps"
            ? "Regenerate Steps"
            : "Regenerate Prompt"}
        </Button>
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
      {FEATURE_LIVE_RUN && runResult ? (
        <div className="mt-4 min-w-0 max-w-full rounded-lg border border-border bg-muted/30 p-4">
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
          {outputPretty?.kind === "json" ? (
            <pre className="mt-3 min-w-0 max-w-full overflow-auto whitespace-pre rounded-md border border-border/50 bg-background/60 p-3 font-mono text-xs leading-5">
              {highlightJson(outputPretty.text)}
            </pre>
          ) : (
            <p className="mt-3 max-h-96 overflow-y-auto whitespace-pre-wrap text-sm leading-6">
              {runResult.output_text}
            </p>
          )}
          <p className="mt-2 font-mono text-[10px] text-muted-foreground">
            {runResult.input_tokens + runResult.output_tokens} tokens ·{" "}
            {runResult.latency_ms} ms
          </p>
        </div>
      ) : null}
      {FEATURE_LIVE_RUN && runError && !runResult ? (
        <p className="mt-3 text-xs text-destructive">{runError}</p>
      ) : null}

      {/* FINISHED STEP / USAGE SIGNALS (Catalog v3, Slice C7) */}
      {step.status === "done" ? (
        <div className="mt-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-3 text-xs text-emerald-800 dark:text-emerald-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" />
            <span className="font-semibold">Step Finished</span>
            {step.handoff_note ? (
              <span className="text-muted-foreground ml-2">
                Note: {step.handoff_note}
              </span>
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
              onAction(
                step,
                "finished",
                note.trim() || undefined,
                feedbackResult,
              );
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
              {b("finished") ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Check className="size-3.5" />
              )}
              Mark Finished
            </Button>
          </form>
        </div>
      )}
    </li>
  );
}
