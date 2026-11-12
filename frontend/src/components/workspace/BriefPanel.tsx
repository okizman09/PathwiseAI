import { Loader2, Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ProductBrief } from "@/lib/api";

function BriefItem({
  label,
  value,
  list,
}: {
  label: string;
  value?: string;
  list?: string[];
}) {
  if (!value && !list?.length) return null;
  return (
    <div className="rounded-lg border border-border/60 bg-muted/20 p-3.5">
      <dt className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1.5 leading-6 text-foreground text-sm">
        {value ?? (
          <ul className="list-disc pl-4 space-y-1">
            {list!.map((i) => (
              <li key={i}>{i}</li>
            ))}
          </ul>
        )}
      </dd>
    </div>
  );
}

export function BriefPanel({
  brief,
  busy,
  isEmailVerified,
  onBuild,
}: {
  brief: ProductBrief;
  busy: string | null;
  isEmailVerified: boolean;
  onBuild: () => void;
}) {
  return (
    <section className="mt-10 rounded-2xl border border-border bg-card p-6 sm:p-8 shadow-sm">
      <p className="eyebrow">Product Brief Finalized</p>
      <h2 className="mt-2 text-2xl font-semibold">{brief.what_being_made}</h2>
      <dl className="mt-6 grid gap-6 text-sm sm:grid-cols-2">
        {brief.product_name ? (
          <BriefItem label="Product Name" value={brief.product_name} />
        ) : null}
        <BriefItem label="Purpose" value={brief.purpose} />
        <BriefItem label="Target Audience" value={brief.target_audience} />
        <BriefItem label="Must Haves" list={brief.must_haves} />
        <BriefItem label="Nice To Haves" list={brief.nice_to_haves} />
        <BriefItem label="Constraints" list={brief.constraints} />
        <BriefItem label="Assumptions" list={brief.assumptions} />
      </dl>
      <div className="mt-8 border-t border-border pt-6">
        <Button
          size="lg"
          className="px-8 shadow-md"
          onClick={onBuild}
          disabled={busy !== null || !isEmailVerified}
        >
          {busy === "workflow" ? (
            <Loader2 className="size-4 animate-spin mr-2" />
          ) : (
            <Wand2 className="size-4 mr-2" />
          )}
          Build My Creation Path
        </Button>
      </div>
    </section>
  );
}
