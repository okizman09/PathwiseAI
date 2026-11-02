import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

import { BrandMark } from "@/components/BrandMark";
import { MarkdownViewer } from "@/components/MarkdownViewer";
import { Button } from "@/components/ui/button";
import privacyContent from "@/content/privacy.md?raw";

export const Route = createFileRoute("/privacy")({
  head: () => ({
    meta: [
      { title: "Privacy Policy — Pathwise AI" },
      { name: "description", content: "Privacy policy and data handling guidelines for Pathwise AI." },
    ],
  }),
  component: PrivacyPage,
});

function PrivacyPage() {
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
          <MarkdownViewer content={privacyContent} />
        </div>
      </main>

      <footer className="border-t border-border/60 py-8 text-center text-xs text-muted-foreground">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-5 sm:px-8">
          <span>© 2026 Pathwise AI</span>
          <div className="flex gap-4">
            <Link to="/terms" className="hover:underline">Terms</Link>
            <Link to="/privacy" className="hover:underline font-semibold text-foreground">Privacy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
