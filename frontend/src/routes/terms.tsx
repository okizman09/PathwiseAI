import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

import { BrandMark } from "@/components/BrandMark";
import { MarkdownViewer } from "@/components/MarkdownViewer";
import { Button } from "@/components/ui/button";
import termsContent from "@/content/terms.md?raw";

export const Route = createFileRoute("/terms")({
  head: () => ({
    meta: [
      { title: "Terms of Service — Pathwise AI" },
      { name: "description", content: "Terms of service and fair usage guidelines for Pathwise AI." },
    ],
  }),
  component: TermsPage,
});

function TermsPage() {
  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border/70 bg-background/95 backdrop-blur-md">
        <div className="mx-auto flex h-[72px] max-w-4xl items-center justify-between px-5 sm:px-8">
          <BrandMark />
          <Button asChild variant="ghost" size="sm" className="gap-2">
            <Link to="/">
              <ArrowLeft className="size-4" />
              <span>Back</span>
            </Link>
          </Button>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-4xl px-5 py-12 sm:px-8">
        <div className="rounded-xl border border-border/70 bg-card p-6 sm:p-10 shadow-sm">
          <MarkdownViewer content={termsContent} />
        </div>
      </main>

      <footer className="border-t border-border/60 py-8 text-center text-xs text-muted-foreground">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-5 sm:px-8">
          <span>© 2026 Pathwise AI</span>
          <div className="flex gap-4">
            <Link to="/terms" className="hover:underline font-semibold text-foreground">Terms</Link>
            <Link to="/privacy" className="hover:underline">Privacy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
