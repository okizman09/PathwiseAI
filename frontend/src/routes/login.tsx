import { createFileRoute, Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";

import { AuthLayout, emailRe, Field, SubmitButton } from "@/components/AuthLayout";
import { supabase } from "@/lib/supabase";
import { api } from "@/lib/api";

export const Route = createFileRoute("/login")({
  validateSearch: (search: Record<string, unknown>): { mode?: "signin" | "signup" } => {
    return {
      mode: search["mode"] === "signup" ? "signup" : "signin",
    };
  },
  head: () => ({
    meta: [
      { title: "Sign in / Sign up — Pathwise" },
      { name: "description", content: "Sign in or create your Pathwise account to start building." },
      { property: "og:title", content: "Sign in / Sign up — Pathwise" },
      { property: "og:description", content: "Sign in or create your Pathwise account to start building." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const search = useSearch({ from: "/login" });
  const [mode, setMode] = useState<"signin" | "signup">(search.mode || "signin");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(false);

  const [msg, setMsg] = useState("");

  const isSignUp = mode === "signup";

  async function handleGoogle() {
    setLoading(true);
    setFormError("");
    setMsg("");
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    if (error) {
      setFormError(error.message);
      setLoading(false);
    }
  }

  async function handleForgotPassword() {
    const fd = new FormData(document.querySelector("form") as HTMLFormElement);
    const email = String(fd.get("email") ?? "").trim();
    if (!email || !emailRe.test(email)) {
      setErrors({ email: "Enter a valid email address to reset password." });
      return;
    }
    
    setLoading(true);
    setFormError("");
    setErrors({});
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
    });
    if (error) {
      setFormError(error.message);
    } else {
      setMsg("Password reset email sent. Check your inbox.");
    }
    setLoading(false);
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const email = String(fd.get("email") ?? "").trim();
    const password = String(fd.get("password") ?? "");
    const next: Record<string, string> = {};

    if (!email) next["email"] = "Enter your email.";
    else if (!emailRe.test(email)) next["email"] = "Enter a valid email address.";

    if (!password) next["password"] = "Enter your password.";
    else if (isSignUp && password.length < 6) next["password"] = "Password must be at least 6 characters.";

    setErrors(next);
    setFormError("");
    setMsg("");
    if (Object.keys(next).length) return;

    setLoading(true);
    try {
      if (isSignUp) {
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
        });
        if (error) throw error;
        setMsg("Success! Check your inbox to verify your email.");
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        
        // Fetch role from backend to decide redirect
        const me = await api.getMe();
        navigate({ to: me.role === "admin" ? "/admin" : "/app" });
      }
    } catch (err: any) {
      setFormError(err?.message || "An error occurred.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title={isSignUp ? "Create your account" : "Welcome to Pathwise"}
      subtitle={
        isSignUp
          ? "Sign up to start building and saving your personalized creation paths."
          : "Sign in to start creating and managing your AI creation paths."
      }
    >
      {/* MODE TABS */}
      <div className="flex rounded-lg border border-border bg-muted/50 p-1 mb-6">
        <button
          type="button"
          onClick={() => {
            setMode("signin");
            setErrors({});
            setFormError("");
            setMsg("");
          }}
          className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${
            !isSignUp
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Sign in
        </button>
        <button
          type="button"
          onClick={() => {
            setMode("signup");
            setErrors({});
            setFormError("");
            setMsg("");
          }}
          className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${
            isSignUp
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Sign up
        </button>
      </div>

      <form className="grid gap-5" onSubmit={onSubmit} noValidate>
        <Field
          id="email"
          label="Email address"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          error={errors["email"]}
        />
        <Field
          id="password"
          label="Password"
          password
          autoComplete={isSignUp ? "new-password" : "current-password"}
          placeholder="••••••••"
          error={errors["password"]}
        />
        {msg ? (
          <p role="alert" className="text-sm text-green-600 dark:text-green-400 font-medium p-3 bg-green-50 dark:bg-green-950/30 rounded-md border border-green-200 dark:border-green-900">
            {msg}
          </p>
        ) : null}
        {formError ? (
          <p role="alert" className="text-sm text-destructive">
            {formError}
          </p>
        ) : null}
        <SubmitButton loading={loading}>
          {isSignUp ? "Create account" : "Sign in"}
        </SubmitButton>
      </form>

      <div className="mt-4 text-center">
        {!isSignUp && (
          <button type="button" onClick={handleForgotPassword} className="text-xs text-muted-foreground hover:text-primary">
            Forgot your password?
          </button>
        )}
      </div>

      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-border"></div>
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">Or continue with</span>
        </div>
      </div>

      <button
        type="button"
        onClick={handleGoogle}
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 rounded-md border border-input bg-background px-4 py-2 text-sm font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="w-5 h-5">
          <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
          <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
          <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
          <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
        </svg>
        Google
      </button>

      <div className="mt-6 text-center text-xs text-muted-foreground">
        {isSignUp && (
          <p className="mb-3 text-[11px] text-muted-foreground">
            By continuing, you agree to Pathwise AI's{" "}
            <Link to="/terms" className="text-primary underline hover:text-primary/80">
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link to="/privacy" className="text-primary underline hover:text-primary/80">
              Privacy Policy
            </Link>
            .
          </p>
        )}
        {isSignUp ? (
          <p>
            Already have an account?{" "}
            <button
              type="button"
              onClick={() => {
                setMode("signin");
                setErrors({});
                setFormError("");
                setMsg("");
              }}
              className="text-primary font-semibold hover:underline"
            >
              Sign in
            </button>
          </p>
        ) : (
          <p>
            Don't have an account?{" "}
            <button
              type="button"
              onClick={() => {
                setMode("signup");
                setErrors({});
                setFormError("");
                setMsg("");
              }}
              className="text-primary font-semibold hover:underline"
            >
              Sign up for free
            </button>
          </p>
        )}
      </div>
    </AuthLayout>
  );
}
