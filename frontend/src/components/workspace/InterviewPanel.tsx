import { ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import type { InterviewAnswer, InterviewQuestionResponse } from "@/lib/api";

export function InterviewPanel({
  question,
  answers,
  busy,
  custom,
  showSkeleton,
  onCustomChange,
  onAnswer,
}: {
  question: InterviewQuestionResponse | null;
  answers: InterviewAnswer[];
  busy: string | null;
  custom: string;
  showSkeleton: boolean;
  onCustomChange: (value: string) => void;
  onAnswer: (nextAnswers: InterviewAnswer[]) => void;
}) {
  return (
    <>
      {/* QUESTION SKELETON (first question still generating) */}
      {showSkeleton ? (
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
            <span className="text-xs text-muted-foreground">
              Step {answers.length + 1}
            </span>
          </div>
          <h2 className="mt-3 text-xl sm:text-2xl font-semibold leading-snug">
            {question.question}
          </h2>

          <div className="mt-6 grid gap-2.5">
            {question.options.map((opt) => (
              <Button
                key={opt}
                variant="outline"
                className="h-auto justify-start whitespace-normal py-3.5 px-4 text-left font-normal hover:border-primary/50 hover:bg-primary/5"
                disabled={busy !== null}
                onClick={() =>
                  onAnswer([
                    ...answers,
                    { question: question.question, answer: opt },
                  ])
                }
              >
                <ChevronRight className="size-4 mr-2 shrink-0 text-muted-foreground" />
                <span>{opt}</span>
              </Button>
            ))}
          </div>

          {question.allow_custom_text ? (
            <div className="mt-4">
              <p className="mb-2 text-xs text-muted-foreground">
                Or write your own specific answer:
              </p>
              <form
                className="flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (custom.trim())
                    onAnswer([
                      ...answers,
                      { question: question.question, answer: custom.trim() },
                    ]);
                }}
              >
                <Input
                  value={custom}
                  onChange={(e) => onCustomChange(e.target.value)}
                  placeholder="Type your answer..."
                  className="bg-background"
                />
                <Button
                  type="submit"
                  disabled={!custom.trim() || busy !== null}
                >
                  Send
                </Button>
              </form>
            </div>
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
    </>
  );
}
