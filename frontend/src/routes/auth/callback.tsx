import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import { api } from "@/lib/api";

export const Route = createFileRoute("/auth/callback")({
  component: AuthCallbackPage,
});

function AuthCallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState("");

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session }, error }) => {
      if (error) {
        setError(error.message);
        return;
      }
      if (!session) {
        setError("No session found. Please log in again.");
        return;
      }

      // We have a session! Check role in backend
      api.getMe()
        .then((me) => {
          navigate({ to: me.role === "admin" ? "/admin" : "/app", replace: true });
        })
        .catch((err) => {
          console.error("Failed to fetch user role:", err);
          // Fallback to /app if role fetch fails
          navigate({ to: "/app", replace: true });
        });
    });
  }, [navigate]);

  return (
    <div className="flex h-screen w-full items-center justify-center p-4">
      {error ? (
        <div className="max-w-md text-center">
          <h1 className="text-xl font-bold mb-4">Authentication Error</h1>
          <p className="text-destructive mb-6">{error}</p>
          <button
            onClick={() => navigate({ to: "/login", replace: true })}
            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
          >
            Back to login
          </button>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
          <p className="text-muted-foreground">Completing sign in...</p>
        </div>
      )}
    </div>
  );
}
