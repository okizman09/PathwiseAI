import { Link } from "@tanstack/react-router";
import { Compass } from "lucide-react";
import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <Link
      to="/"
      className={cn("group inline-flex items-center gap-2.5 cursor-pointer select-none", className)}
      aria-label="Pathwise home"
    >
      <span className="relative grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground shadow-xs transition-all duration-300 group-hover:scale-105 group-hover:bg-primary/90 group-hover:shadow-sm">
        <Compass
          className="size-[18px] transition-transform duration-700 ease-[cubic-bezier(0.34,1.56,0.64,1)] group-hover:rotate-[360deg]"
          strokeWidth={1.8}
        />
      </span>
      <span className="text-[17px] font-semibold text-foreground tracking-tight transition-colors duration-200 group-hover:text-primary">
        Pathwise
      </span>
    </Link>
  );
}
