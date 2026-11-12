import { AlertCircle, Check, CheckCircle2, DollarSign } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { WorkflowResponse } from "@/lib/api";
import { FEATURE_LIVE_RUN } from "@/lib/features";
import { StepCard } from "./StepCard";
import type { StepActionHandler } from "./types";

export function WorkflowView({
  workflow,
  busy,
  onAction,
}: {
  workflow: WorkflowResponse;
  busy: string | null;
  onAction: StepActionHandler;
}) {
  return (
    <section className="mt-10 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="eyebrow">Verified Workflow Path</p>
          <h2 className="mt-1 text-2xl font-bold">
            {`${workflow.steps.length} Sequenced Action Step${workflow.steps.length === 1 ? "" : "s"}`}
          </h2>
        </div>
      </div>

      {/* COST SUMMARY (Catalog v3, Slice C5) */}
      {workflow.cost_summary ? (
        <div className="rounded-2xl border border-border bg-card p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <DollarSign className="size-4 text-primary" />
              <h3 className="text-sm font-bold text-foreground">
                Estimated Workflow Cost
              </h3>
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
                  May Incur Costs
                  {workflow.cost_summary.estimated_monthly_usd
                    ? ` (~$${workflow.cost_summary.estimated_monthly_usd}/mo)`
                    : ""}
                </span>
              </Badge>
            )}
          </div>

          {workflow.cost_summary.notes &&
            workflow.cost_summary.notes.length > 0 && (
              <ul className="text-xs text-muted-foreground space-y-1 list-disc pl-4 pt-1">
                {workflow.cost_summary.notes.map((note, idx) => (
                  <li key={idx} className="leading-relaxed">
                    {note}
                  </li>
                ))}
              </ul>
            )}
        </div>
      ) : null}

      {FEATURE_LIVE_RUN &&
      workflow.brief.budget_preference === "free_only" &&
      workflow.steps.every((step) => !step.can_run) ? (
        <p className="text-xs text-muted-foreground">
          Tip: this free-only budget excludes the models that power live runs. A
          flexible budget unlocks them (10 runs/day).
        </p>
      ) : null}

      <ol className="grid gap-6">
        {workflow.steps.map((step) => (
          <StepCard
            key={step.step_id}
            step={step}
            workflowId={workflow.id}
            busy={busy}
            onAction={onAction}
          />
        ))}
      </ol>

      {workflow.steps.length > 0 &&
      workflow.steps.every((step) => step.status === "done") ? (
        <div className="rounded-2xl border border-emerald-500/25 bg-emerald-500/10 p-5 sm:p-6">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <h3 className="text-base font-semibold text-foreground">
              {`You finished all ${workflow.steps.length} step${workflow.steps.length === 1 ? "" : "s"}`}
            </h3>
          </div>
          <ul className="mt-3 space-y-1.5">
            {workflow.steps.map((step) => (
              <li key={step.step_id} className="flex items-start gap-2 text-sm">
                <Check className="size-4 mt-0.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                <span>
                  <span className="font-medium text-foreground">
                    {step.job}
                  </span>
                  {step.handoff_note ? (
                    <span className="text-muted-foreground">
                      {" "}
                      — {step.handoff_note}
                    </span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
