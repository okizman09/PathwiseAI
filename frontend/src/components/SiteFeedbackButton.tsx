import { useState, type FormEvent } from "react";
import { CheckCircle2, Loader2, MessageSquare } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";

const MAX_MESSAGE = 2000;

export function SiteFeedbackButton() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [contact, setContact] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  function reset() {
    setMessage("");
    setContact("");
    setError("");
    setSent(false);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!message.trim() || sending) return;
    setSending(true);
    setError("");
    try {
      await api.submitSiteFeedback({
        message: message.trim(),
        contact: contact.trim() || undefined,
        page: window.location.pathname,
      });
      setSent(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Couldn't send feedback. Please try again.",
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) reset();
      }}
    >
      <DialogTrigger asChild>
        <button
          type="button"
          className="fixed right-[max(1.25rem,env(safe-area-inset-right))] bottom-[max(1.25rem,env(safe-area-inset-bottom))] z-40 inline-flex h-11 items-center gap-2 rounded-full border border-border bg-card px-4 text-sm font-medium shadow-lg hover:border-primary/40"
        >
          <MessageSquare className="size-4 text-primary" />
          Feedback
        </button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        {sent ? (
          <div className="py-6 text-center">
            <CheckCircle2 className="mx-auto size-10 text-emerald-600 dark:text-emerald-400" />
            <DialogTitle className="mt-3">Thanks for the feedback</DialogTitle>
            <DialogDescription className="mt-1">
              We read everything. It shapes what we build next.
            </DialogDescription>
            <Button className="mt-5" onClick={() => setOpen(false)}>
              Done
            </Button>
          </div>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Share feedback</DialogTitle>
              <DialogDescription>
                Tell us what&apos;s working, what&apos;s confusing, or
                what&apos;s missing.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={submit} className="mt-2 grid gap-3">
              <div>
                <Textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="e.g. The sample workflow sold me, but I wasn't sure where to start…"
                  rows={4}
                  maxLength={MAX_MESSAGE}
                  className="resize-none bg-background"
                />
                <p className="mt-1 text-right text-[11px] text-muted-foreground">
                  {message.length}/{MAX_MESSAGE}
                </p>
              </div>
              <Input
                value={contact}
                onChange={(e) => setContact(e.target.value)}
                placeholder="Email (optional, for a reply)"
                type="email"
                className="bg-background"
              />
              {error ? (
                <p role="alert" className="text-xs text-destructive">
                  {error}
                </p>
              ) : null}
              <Button type="submit" disabled={!message.trim() || sending}>
                {sending ? (
                  <Loader2 className="size-4 animate-spin mr-2" />
                ) : null}
                Send feedback
              </Button>
            </form>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
