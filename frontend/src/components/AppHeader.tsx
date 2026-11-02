import { Link, useNavigate } from "@tanstack/react-router";
import { LayoutGrid, LogOut, MessageSquare, ShieldCheck, Trash2, WandSparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { BrandMark } from "@/components/BrandMark";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export interface UserSession {
  email?: string;
  role?: string;
}

export function AppHeader({ session }: { session: UserSession }) {
  const navigate = useNavigate();
  const [isDeleting, setIsDeleting] = useState(false);
  const feedbackUrl = (import.meta.env as Record<string, string | undefined>)["VITE_FEEDBACK_URL"] || "";

  async function handleDeleteAccount() {
    setIsDeleting(true);
    try {
      await api.deleteAccount();
      await supabase.auth.signOut();
      toast.success("Account deleted permanently.");
      navigate({ to: "/login", search: { mode: "signin" }, replace: true });
    } catch (err: any) {
      toast.error(err?.message || "Failed to delete account. Please try again.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/95 backdrop-blur-md">
      <div className="mx-auto flex h-[72px] max-w-[1440px] items-center gap-8 px-5 sm:px-8 lg:px-12">
        <BrandMark />
        <nav className="flex items-center gap-6 text-sm">
          <Link
            to="/app"
            className="nav-link inline-flex items-center gap-1.5"
            activeProps={{ className: "text-foreground font-semibold" }}
          >
            <WandSparkles className="size-3.5" />
            <span>Workspace</span>
          </Link>
          <Link
            to="/tools"
            className="nav-link inline-flex items-center gap-1.5"
            activeProps={{ className: "text-foreground font-semibold" }}
          >
            <LayoutGrid className="size-3.5" />
            <span>Directory</span>
          </Link>
          {session.role === "admin" ? (
            <Link
              to="/admin"
              className="nav-link inline-flex items-center gap-1.5 text-emerald-600 font-medium hover:text-emerald-700"
              activeProps={{ className: "text-emerald-700 font-semibold" }}
            >
              <ShieldCheck className="size-3.5" />
              <span>Admin Catalog</span>
            </Link>
          ) : null}
          {feedbackUrl ? (
            <a
              href={feedbackUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="nav-link inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
            >
              <MessageSquare className="size-3.5" />
              <span>Feedback</span>
            </a>
          ) : null}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <span className="hidden text-xs text-muted-foreground sm:inline font-mono bg-muted/50 px-2.5 py-1 rounded-md">
            {session.email}
          </span>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-9 gap-1.5 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                title="Permanently delete account"
              >
                <Trash2 className="size-3.5" />
                <span className="hidden md:inline">Delete account</span>
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                <AlertDialogDescription>
                  This action cannot be undone. This will permanently delete your account, saved creation paths, step actions, daily usage, and authentication records from Pathwise AI.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={(e) => {
                    e.preventDefault();
                    handleDeleteAccount();
                  }}
                  disabled={isDeleting}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {isDeleting ? "Deleting..." : "Yes, delete my account"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          <Button
            variant="ghost"
            size="sm"
            onClick={async () => {
              await supabase.auth.signOut();
              navigate({ to: "/login", search: { mode: "signin" }, replace: true });
            }}
            className="h-9 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <LogOut className="size-3.5" />
            <span>Sign out</span>
          </Button>
        </div>
      </div>
    </header>
  );
}
