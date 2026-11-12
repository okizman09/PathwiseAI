import type { WorkflowStep } from "@/lib/api";

export type StepActionKind =
  "regenerate" | "switch_tool" | "finished" | "recheck";

export type StepFeedbackResult = "worked" | "partly" | "didnt";

export type StepActionHandler = (
  step: WorkflowStep,
  action: StepActionKind,
  payload?: string,
  feedbackResult?: StepFeedbackResult,
) => void;
