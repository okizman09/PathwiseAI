import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useState, type ReactNode } from "react";

import { BrandMark } from "@/components/BrandMark";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <main className="flex min-h-screen flex-col bg-background">
      <header className="border-b border-border/70 bg-background/95 backdrop-blur-md">
        <div className="mx-auto flex h-[72px] max-w-[1440px] items-center px-5 sm:px-8 lg:px-12">
          <BrandMark />
        </div>
      </header>
      <div className="flex flex-1 items-center justify-center px-5 py-12 sm:py-16">
        <div className="w-full max-w-[420px] rounded-2xl border border-border bg-card p-6 sm:p-8 shadow-sm">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">{title}</h1>
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{subtitle}</p>
          <div className="mt-6">{children}</div>
          {footer ? <p className="mt-6 text-xs text-muted-foreground text-center">{footer}</p> : null}
        </div>
      </div>
    </main>
  );
}

export function Field({
  id,
  label,
  error,
  password,
  ...props
}: {
  id: string;
  label: string;
  error?: string | undefined;
  password?: boolean;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  const [show, setShow] = useState(false);
  return (
    <div className="grid gap-2">
      <Label htmlFor={id} className="text-xs font-medium">{label}</Label>
      <div className="relative">
        <Input
          id={id}
          name={id}
          type={password ? (show ? "text" : "password") : props.type}
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-error` : undefined}
          className="h-10 bg-background pr-12 text-sm"
          {...props}
        />
        {password ? (
          <button
            type="button"
            onClick={() => setShow((v) => !v)}
            className="absolute inset-y-0 right-3 inline-flex items-center text-xs font-medium text-muted-foreground hover:text-foreground"
            aria-label={show ? "Hide password" : "Show password"}
          >
            {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        ) : null}
      </div>
      {error ? (
        <p id={`${id}-error`} className="text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function SubmitButton({ loading, children }: { loading: boolean; children: ReactNode }) {
  return (
    <Button type="submit" disabled={loading} className="h-10 w-full rounded-lg text-sm font-semibold shadow-[var(--shadow-button)]">
      {loading ? <Loader2 className="size-4 animate-spin mr-2" /> : null}
      {children}
    </Button>
  );
}

export const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
