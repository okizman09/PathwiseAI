import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import {
  AlertCircle,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCircle2,
  Code2,
  Copy,
  ExternalLink,
  Filter,
  Globe,
  Layers,
  LayoutGrid,
  Loader2,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { BrandMark } from "@/components/BrandMark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  api,
  getApiBaseUrl,
  type TaxonomyPayload,
  type ToolResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { supabase } from "@/lib/supabase";

export const Route = createFileRoute("/tools")({
  head: () => ({
    meta: [
      { title: "Tool Directory — Pathwise" },
      {
        name: "description",
        content:
          "Discover verified AI tools, transparent pricing models, and tested prompt styles across all 9 creator domains.",
      },
      { property: "og:title", content: "Pathwise AI Tool Directory" },
      {
        property: "og:description",
        content:
          "Verified AI tools, pricing breakdowns, and prompt engineering flash cards.",
      },
    ],
  }),
  component: ToolsPage,
});

const FALLBACK_DOMAINS = [
  { slug: "all", label: "All Domains" },
  { slug: "models", label: "Models" },
  { slug: "meta", label: "Meta" },
  { slug: "software", label: "Software engineering" },
  { slug: "builders", label: "No-code & app builders" },
  { slug: "design", label: "Design & visual arts" },
  { slug: "video", label: "Video production" },
  { slug: "audio", label: "Audio & music" },
  { slug: "writing", label: "Writing & editorial" },
  { slug: "research", label: "Research & knowledge" },
  { slug: "deploy_backend", label: "Hosting & infrastructure" },
  { slug: "freelance_ops", label: "Freelance business ops" },
];

const PRICING_OPTIONS = [
  { value: "all", label: "All Pricing" },
  { value: "free", label: "Free" },
  { value: "freemium", label: "Freemium" },
  { value: "free_trial", label: "Free trial" },
  { value: "paid", label: "Paid" },
  { value: "open_source", label: "Open source" },
];

function formatPricingLabel(model?: string): { label: string; className: string } {
  const m = (model || "").toLowerCase();
  switch (m) {
    case "free":
      return {
        label: "Free",
        className: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20",
      };
    case "freemium":
      return {
        label: "Freemium",
        className: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20",
      };
    case "free_trial":
      return {
        label: "Free Trial",
        className: "bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/20",
      };
    case "open_source":
      return {
        label: "Open Source",
        className: "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border-indigo-500/20",
      };
    case "paid":
      return {
        label: "Paid",
        className: "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20",
      };
    default:
      return {
        label: model ? model.replace("_", " ") : "Freemium",
        className: "bg-muted text-muted-foreground border-border",
      };
  }
}

function formatKindLabel(kind?: string | null): string | null {
  switch ((kind || "").toLowerCase()) {
    case "runnable":
      return "Runnable";
    case "open_weight":
      return "Open-weight";
    case "developer_tool":
      return "Developer tool";
    case "platform":
      return "Platform";
    default:
      return kind ? kind.replace(/_/g, " ") : null;
  }
}

function formatShortDate(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function ToolLogo({
  logoUrl,
  name,
  className,
}: {
  logoUrl?: string | null | undefined;
  name: string;
  className?: string;
}) {
  const [error, setError] = useState(false);
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || "")
    .join("") || name.slice(0, 2).toUpperCase();

  if (logoUrl && !error) {
    return (
      <div
        className={cn(
          "size-10 rounded-xl overflow-hidden bg-card border border-border/80 flex items-center justify-center shrink-0 shadow-xs",
          className
        )}
      >
        <img
          src={logoUrl}
          alt={`${name} logo`}
          loading="lazy"
          onError={() => setError(true)}
          className="size-full object-contain p-1"
        />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "size-10 rounded-xl bg-primary/10 text-primary font-bold text-xs flex items-center justify-center shrink-0 border border-primary/20 shadow-xs",
        className
      )}
    >
      {initials}
    </div>
  );
}

function ToolsPage() {
  const navigate = useNavigate();
  const [session, setSession] = useState<any>(null);

  // Filter states
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDomain, setSelectedDomain] = useState("all");
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [selectedPricing, setSelectedPricing] = useState("all");
  const [onlyHasFreeTier, setOnlyHasFreeTier] = useState(false);
  const [onlyNoCreditCard, setOnlyNoCreditCard] = useState(false);
  const [onlyCommercialFree, setOnlyCommercialFree] = useState(false);
  const onlyMeta = selectedDomain === "meta";

  // Selected tool modal
  const [activeModalTool, setActiveModalTool] = useState<ToolResponse | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });
    return () => subscription.unsubscribe();
  }, []);

  // Fetch taxonomy
  const { data: taxonomy } = useQuery<TaxonomyPayload>({
    queryKey: ["taxonomy"],
    queryFn: () => api.getTaxonomy(),
    staleTime: 1000 * 60 * 60, // 1 hour
  });

  // Fetch verified public tools
  const {
    data: tools,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["public-tools", onlyMeta ? "meta" : "all"],
    queryFn: () => api.getTools(onlyMeta ? { ecosystem: "meta" } : undefined),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  // Domains list for tabs
  const domainTabs = useMemo(() => {
    if (taxonomy?.domains?.length) {
      return [
        { slug: "all", label: "All Domains" },
        { slug: "models", label: "Models" },
        { slug: "meta", label: "Meta" },
        ...taxonomy.domains.map((d) => ({ slug: d.slug, label: d.label })),
      ];
    }
    return FALLBACK_DOMAINS;
  }, [taxonomy]);

  // Jobs available for current selected domain
  const availableJobsForDomain = useMemo(() => {
    if (
      selectedDomain === "all" ||
      selectedDomain === "models" ||
      selectedDomain === "meta" ||
      !taxonomy?.domains
    )
      return [];
    const domainDef = taxonomy.domains.find((d) => d.slug === selectedDomain);
    if (!domainDef || !domainDef.jobs) return [];
    return domainDef.jobs.map((jobSlug) => ({
      slug: jobSlug,
      label: taxonomy.job_labels?.[jobSlug] || jobSlug.replace(/_/g, " "),
    }));
  }, [selectedDomain, taxonomy]);

  // Clear job selection when domain changes
  const handleDomainSelect = (domainSlug: string) => {
    setSelectedDomain(domainSlug);
    setSelectedJob(null);
  };

  // Reset all filters
  const handleResetFilters = () => {
    setSearchQuery("");
    setSelectedDomain("all");
    setSelectedJob(null);
    setSelectedPricing("all");
    setOnlyHasFreeTier(false);
    setOnlyNoCreditCard(false);
    setOnlyCommercialFree(false);
  };

  const hasActiveFilters =
    Boolean(searchQuery.trim()) ||
    selectedDomain !== "all" ||
    selectedJob !== null ||
    selectedPricing !== "all" ||
    onlyHasFreeTier ||
    onlyNoCreditCard ||
    onlyCommercialFree;

  // Filtered & Sorted Tools
  const filteredTools = useMemo(() => {
    if (!tools) return [];

    const q = searchQuery.trim().toLowerCase();

    const filtered = tools.filter((tool) => {
      // Domain / collection filter
      if (selectedDomain === "models") {
        if (!tool.kind) return false;
      } else if (selectedDomain === "meta") {
        if (tool.ecosystem !== "meta") return false;
      } else if (selectedDomain !== "all") {
        const toolDomain = tool.domain?.toLowerCase();
        if (toolDomain !== selectedDomain.toLowerCase()) return false;
      }

      // Job filter
      if (selectedJob) {
        if (!tool.jobs || !tool.jobs.includes(selectedJob)) return false;
      }

      // Pricing model filter
      if (selectedPricing !== "all") {
        const pm = (tool.pricing_model || "unknown").toLowerCase();
        if (pm !== selectedPricing.toLowerCase()) return false;
      }

      // Has free tier toggle
      if (onlyHasFreeTier && tool.has_free_tier !== true) {
        return false;
      }

      // No credit card required toggle
      if (onlyNoCreditCard && tool.credit_card_required === true) {
        return false;
      }

      // Commercial use on free plan toggle
      if (onlyCommercialFree && tool.commercial_use_on_free !== true) {
        return false;
      }

      // Search query (name, tagline, summary, jobs)
      if (q) {
        const matchesName = tool.name.toLowerCase().includes(q);
        const matchesTagline = Boolean(tool.tagline?.toLowerCase().includes(q));
        const matchesSummary = Boolean(tool.summary?.toLowerCase().includes(q));
        const matchesJobs = Boolean(tool.jobs?.some((j) => j.toLowerCase().includes(q)));
        if (!matchesName && !matchesTagline && !matchesSummary && !matchesJobs) {
          return false;
        }
      }

      return true;
    });

    // Sort: Pathwise picks first, then name alphabetically
    return filtered.sort((a, b) => {
      const aPick = a.is_pick ? 1 : 0;
      const bPick = b.is_pick ? 1 : 0;
      if (bPick !== aPick) return bPick - aPick;
      return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
    });
  }, [
    tools,
    searchQuery,
    selectedDomain,
    selectedJob,
    selectedPricing,
    onlyHasFreeTier,
    onlyNoCreditCard,
    onlyCommercialFree,
  ]);

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 border-b border-border/70 bg-background/95 backdrop-blur-md">
        <div className="mx-auto flex h-[72px] max-w-[1440px] items-center gap-8 px-5 sm:px-8 lg:px-12">
          <BrandMark />
          <nav className="flex items-center gap-6 text-sm">
            <Link
              to="/tools"
              className="nav-link inline-flex items-center gap-1.5 text-foreground font-semibold"
            >
              <LayoutGrid className="size-3.5" />
              <span>Directory</span>
            </Link>
          </nav>
          <div className="ml-auto flex items-center gap-4">
            {session ? (
              <Button onClick={() => navigate({ to: "/app" })} variant="default" size="sm">
                Go to Workspace
              </Button>
            ) : (
              <Button onClick={() => navigate({ to: "/login" })} variant="default" size="sm">
                Sign In
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 mx-auto w-full max-w-[1440px] px-5 py-8 sm:px-8 lg:px-12">
        {/* Header Title Section */}
        <div className="mb-8 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 border-b border-border/50 pb-8">
          <div>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
              AI Tools Directory
            </h1>
            <p className="mt-2 text-base text-muted-foreground max-w-2xl leading-relaxed">
              Explore verified creative tools, transparent free tier breakdowns, and tested prompt
              styles across nine creator domains.
            </p>
          </div>

          {/* Search Box */}
          <div className="w-full lg:w-96 relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search name, tagline, jobs..."
              className="pl-10 pr-9 h-11 rounded-xl bg-card border-border shadow-xs"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label="Clear search"
              >
                <X className="size-4" />
              </button>
            )}
          </div>
        </div>

        {/* Domain Tabs Navigation (9 Domains from Taxonomy) */}
        <div className="mb-6">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-2 scrollbar-none border-b border-border/40">
            {domainTabs.map((domain) => {
              const active = selectedDomain === domain.slug;
              return (
                <button
                  key={domain.slug}
                  type="button"
                  onClick={() => handleDomainSelect(domain.slug)}
                  className={cn(
                    "whitespace-nowrap px-4 py-2 text-xs font-semibold rounded-lg transition-all duration-200 shrink-0",
                    active
                      ? "bg-primary text-primary-foreground shadow-xs"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                  )}
                >
                  {domain.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Job Chips for Selected Domain */}
        {availableJobsForDomain.length > 0 && (
          <div className="mb-6 p-4 rounded-xl bg-muted/30 border border-border/60">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2.5 flex items-center gap-1.5">
              <Filter className="size-3 text-primary" />
              <span>Jobs in {domainTabs.find((d) => d.slug === selectedDomain)?.label}:</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setSelectedJob(null)}
                className={cn(
                  "text-xs px-3 py-1.5 rounded-full transition-colors border",
                  selectedJob === null
                    ? "bg-foreground text-background border-foreground font-semibold"
                    : "bg-background text-muted-foreground border-border hover:border-foreground/40 hover:text-foreground"
                )}
              >
                All jobs
              </button>
              {availableJobsForDomain.map((job) => {
                const active = selectedJob === job.slug;
                return (
                  <button
                    key={job.slug}
                    type="button"
                    onClick={() => setSelectedJob(active ? null : job.slug)}
                    className={cn(
                      "text-xs px-3 py-1.5 rounded-full transition-colors border",
                      active
                        ? "bg-primary text-primary-foreground border-primary font-semibold"
                        : "bg-background text-muted-foreground border-border hover:border-primary/50 hover:text-foreground"
                    )}
                  >
                    {job.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Filter Controls Row (Pricing Pills + Toggles) */}
        <div className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-xl bg-card border border-border">
          {/* Pricing Model Selector */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0 scrollbar-none">
            <span className="text-xs font-semibold text-muted-foreground shrink-0 mr-1">
              Pricing:
            </span>
            {PRICING_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setSelectedPricing(opt.value)}
                className={cn(
                  "text-xs px-2.5 py-1 rounded-md transition-colors shrink-0",
                  selectedPricing === opt.value
                    ? "bg-secondary text-secondary-foreground font-semibold"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Quick Toggles */}
          <div className="flex flex-wrap items-center gap-4 sm:gap-6 border-t md:border-t-0 pt-3 md:pt-0 border-border/60">
            <button
              type="button"
              onClick={() => handleDomainSelect(onlyMeta ? "all" : "meta")}
              aria-pressed={onlyMeta}
              className={cn(
                "text-xs px-3 py-1.5 rounded-full transition-colors border",
                onlyMeta
                  ? "bg-primary text-primary-foreground border-primary font-semibold"
                  : "bg-background text-muted-foreground border-border hover:border-primary/50 hover:text-foreground",
              )}
            >
              Meta only
            </button>
            <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-foreground select-none">
              <Switch
                checked={onlyHasFreeTier}
                onCheckedChange={setOnlyHasFreeTier}
              />
              <span>Has free tier</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-foreground select-none">
              <Switch
                checked={onlyNoCreditCard}
                onCheckedChange={setOnlyNoCreditCard}
              />
              <span>No credit card</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-foreground select-none">
              <Switch
                checked={onlyCommercialFree}
                onCheckedChange={setOnlyCommercialFree}
              />
              <span>Commercial use on free</span>
            </label>

            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleResetFilters}
                className="h-8 text-xs text-muted-foreground hover:text-foreground gap-1.5 px-2"
              >
                <RotateCcw className="size-3" />
                <span>Reset</span>
              </Button>
            )}
          </div>
        </div>

        {/* Directory Tools Grid */}
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-28 gap-3">
            <Loader2 className="size-8 animate-spin text-primary" />
            <p className="text-sm font-medium text-muted-foreground">
              Loading verified catalog tools...
            </p>
          </div>
        ) : isError ? (
          <div className="rounded-2xl border border-destructive/20 bg-destructive/10 p-10 text-center text-destructive">
            <AlertCircle className="size-8 mx-auto mb-2 text-destructive" />
            <p className="font-semibold text-base">Failed to load verified tools catalog.</p>
            <p className="text-sm mt-1 text-muted-foreground">
              Please check your connection and try again.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              className="mt-4"
            >
              Retry
            </Button>
          </div>
        ) : filteredTools.length > 0 ? (
          <div>
            <div className="mb-4 flex items-center justify-between text-xs text-muted-foreground font-medium">
              <span>
                Showing {filteredTools.length} {filteredTools.length === 1 ? "tool" : "tools"}
              </span>
              <span>Sorted by: Pathwise Picks first, then name</span>
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {filteredTools.map((tool) => (
                <ToolCatalogCard
                  key={tool.id}
                  tool={tool}
                  jobLabels={taxonomy?.job_labels}
                  onOpenDetails={() => setActiveModalTool(tool)}
                />
              ))}
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-border p-16 text-center bg-card/40">
            <div className="mx-auto size-12 rounded-full bg-muted flex items-center justify-center text-muted-foreground mb-3">
              <Layers className="size-6" />
            </div>
            <h3 className="text-base font-semibold text-foreground">No matching tools found</h3>
            <p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
              No verified tools matched your selected filters. Try broadening your domain, job,
              or toggle criteria.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={handleResetFilters}
              className="mt-4 gap-1.5"
            >
              <RotateCcw className="size-3.5" />
              <span>Reset all filters</span>
            </Button>
          </div>
        )}
      </main>

      {/* Directory Footer */}
      <footer className="mt-16 border-t border-border/60 py-8 text-center text-xs text-muted-foreground">
        <p>Logos belong to their respective owners.</p>
      </footer>

      {/* Card Info Modal Dialog */}
      {activeModalTool && (
        <ToolDetailsDialog
          tool={activeModalTool}
          jobLabels={taxonomy?.job_labels}
          open={Boolean(activeModalTool)}
          onOpenChange={(isOpen) => !isOpen && setActiveModalTool(null)}
        />
      )}
    </div>
  );
}

function getToolDescription(tool: ToolResponse, jobLabels?: Record<string, string>): string {
  if (tool.tagline && tool.tagline.trim().length > 0) {
    return tool.tagline.trim();
  }
  if (tool.summary && tool.summary.trim().length > 0) {
    return tool.summary.trim();
  }
  if (tool.best_for && tool.best_for.trim().length > 0) {
    return tool.best_for.trim();
  }
  if (tool.jobs && tool.jobs.length > 0) {
    const rawJobs = tool.jobs.slice(0, 3).map((j) => {
      const lbl = jobLabels?.[j] || j.replace(/_/g, " ");
      return lbl;
    });
    const phrase =
      rawJobs.length === 1
        ? rawJobs[0]
        : rawJobs.length === 2
          ? `${rawJobs[0]} and ${rawJobs[1]}`
          : `${rawJobs[0]}, ${rawJobs[1]}, and ${rawJobs[2]}`;
    return `AI tool specialized in ${phrase}.`;
  }
  if (tool.domain) {
    return `Verified AI tool for ${tool.domain.replace(/_/g, " ")}.`;
  }
  return "Verified AI tool for creative workflows.";
}

/**
 * Tool Catalog Card Component (Catalog v3 Card)
 */
function ToolCatalogCard({
  tool,
  jobLabels,
  onOpenDetails,
}: {
  tool: ToolResponse;
  jobLabels?: Record<string, string> | undefined;
  onOpenDetails: () => void;
}) {
  const pricingInfo = formatPricingLabel(tool.pricing_model);
  const verifiedBadgeText =
    tool.verified_badge || tool.verified_at ? "Verified" : null;
  const description = getToolDescription(tool, jobLabels);

  return (
    <Card className="group flex flex-col h-full rounded-2xl border border-border/80 bg-card hover:border-primary/40 hover:shadow-lg transition-all duration-300 overflow-hidden">
      <CardHeader className="pb-3 pt-5 px-5 space-y-3">
        {/* Top Badges Row: Pick Badge & Verified Badge */}
        <div className="flex items-center justify-between gap-2 min-h-5">
          <div className="flex items-center gap-1.5 flex-wrap">
            {tool.is_pick && (
              <Badge className="bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30 gap-1 text-[10px] font-semibold py-0.5">
                <Sparkles className="size-3 text-amber-500 fill-amber-500" />
                <span>Pathwise Pick</span>
              </Badge>
            )}
            {verifiedBadgeText && (
              <Badge
                variant="outline"
                className="text-[10px] font-medium text-emerald-700 dark:text-emerald-400 border-emerald-500/30 bg-emerald-500/5 gap-1 py-0.5"
              >
                <ShieldCheck className="size-3 text-emerald-500" />
                <span>{verifiedBadgeText}</span>
              </Badge>
            )}
            {tool.used_in_workflows_count != null && tool.used_in_workflows_count >= 10 && (
              <Badge
                variant="outline"
                className="text-[10px] font-medium text-primary border-primary/30 bg-primary/5 gap-1 py-0.5"
              >
                <span>Used in {tool.used_in_workflows_count} workflows</span>
              </Badge>
            )}
            {tool.ecosystem === "meta" && (
              <Badge className="bg-sky-500/15 text-sky-700 dark:text-sky-300 border-sky-500/30 gap-1 text-[10px] font-semibold py-0.5">
                <span>Meta</span>
              </Badge>
            )}
            {tool.ecosystem === "meta" && formatKindLabel(tool.kind) && (
              <Badge
                variant="outline"
                className="text-[10px] font-medium text-muted-foreground border-border gap-1 py-0.5"
              >
                <span>{formatKindLabel(tool.kind)}</span>
              </Badge>
            )}
          </div>

          {/* Price badge: hidden when pricing is unknown */}
          {tool.pricing_model && tool.pricing_model !== "unknown" && pricingInfo && (
            <Badge
              variant="outline"
              className={cn("text-[10px] font-semibold shrink-0 py-0.5", pricingInfo.className)}
            >
              {pricingInfo.label}
            </Badge>
          )}
        </div>

        {/* Identity Row: Logo + Name */}
        <div className="flex items-center gap-3">
          <ToolLogo logoUrl={tool.logo_url} name={tool.name} />
          <div className="min-w-0 flex-1">
            <CardTitle
              className="text-base font-bold tracking-tight text-foreground truncate cursor-pointer group-hover:text-primary transition-colors"
              onClick={onOpenDetails}
              title={tool.name}
            >
              {tool.name}
            </CardTitle>
            {tool.domain && (
              <span className="text-[11px] text-muted-foreground capitalize">
                {tool.domain.replace("_", " ")}
              </span>
            )}
          </div>
        </div>

        {/* Tagline / Description */}
        <p className="text-xs text-foreground/80 line-clamp-2 min-h-8 leading-relaxed" title={description}>
          {description}
        </p>

        {/* Free Tier Summary One-Liner */}
        {tool.has_free_tier && tool.free_tier_summary && (
          <div className="rounded-lg bg-emerald-500/5 border border-emerald-500/15 px-2.5 py-1.5 text-[11px] text-emerald-800 dark:text-emerald-300">
            <span className="font-semibold">Free tier: </span>
            <span className="line-clamp-1">{tool.free_tier_summary}</span>
          </div>
        )}
      </CardHeader>

      <CardContent className="flex-1 flex flex-col justify-end px-5 pb-4 pt-1">
        {/* Job Chips (Up to 3 chips + counter) */}
        {tool.jobs && tool.jobs.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap pt-2">
            {tool.jobs.slice(0, 3).map((jobSlug) => {
              const label = jobLabels?.[jobSlug] || jobSlug.replace(/_/g, " ");
              return (
                <Badge
                  key={jobSlug}
                  variant="outline"
                  className="text-[10px] text-muted-foreground font-normal bg-muted/30 border-border truncate max-w-[140px]"
                  title={label}
                >
                  {label}
                </Badge>
              );
            })}
            {tool.jobs.length > 3 && (
              <Badge
                variant="outline"
                className="text-[10px] text-muted-foreground font-mono px-1.5"
              >
                +{tool.jobs.length - 3}
              </Badge>
            )}
          </div>
        )}
      </CardContent>

      <CardFooter className="flex flex-col gap-2.5 px-5 py-4 border-t border-border/60 bg-muted/15 rounded-b-2xl">
        <div className="flex flex-col gap-2 w-full">
          <Button
            asChild
            variant="default"
            size="sm"
            className="w-full h-9 text-xs font-semibold gap-1.5 shadow-xs cursor-pointer"
          >
            <a
              href={`${getApiBaseUrl()}${tool.go_path || `/go/${tool.id}`}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <span>Open tool</span>
              <ExternalLink className="size-3.5" />
            </a>
          </Button>

          <div className="flex items-center gap-2 w-full">
            <Button
              variant="outline"
              size="sm"
              onClick={onOpenDetails}
              className="flex-1 h-8 text-xs font-medium gap-1.5 hover:bg-background cursor-pointer"
            >
              <BookOpen className="size-3.5 text-muted-foreground" />
              <span>Card info</span>
            </Button>

            {tool.docs_url && (
              <Button
                asChild
                variant="outline"
                size="sm"
                className="flex-1 h-8 text-xs font-medium gap-1.5 hover:bg-background cursor-pointer"
              >
                <a
                  href={tool.docs_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={`${tool.name} Documentation`}
                >
                  <span>Docs</span>
                  <ExternalLink className="size-3 text-muted-foreground" />
                </a>
              </Button>
            )}
          </div>
        </div>

      </CardFooter>
    </Card>
  );
}

function ToolPreviewBanner({
  ogImageUrl,
  name,
}: {
  ogImageUrl?: string | null;
  name: string;
}) {
  const [error, setError] = useState(false);
  if (!ogImageUrl || error) return null;

  return (
    <div className="relative w-full h-36 sm:h-44 -mt-5 -mx-5 sm:-mt-7 sm:-mx-7 mb-4 overflow-hidden rounded-t-2xl bg-muted/30 border-b border-border/60">
      <img
        src={ogImageUrl}
        alt={`${name} preview`}
        loading="lazy"
        onError={() => setError(true)}
        className="w-full h-full object-cover"
      />
    </div>
  );
}

/**
 * Detailed Card Info Modal Dialog (Slice C4 Requirements)
 */
function ToolDetailsDialog({
  tool,
  jobLabels,
  open,
  onOpenChange,
}: {
  tool: ToolResponse;
  jobLabels?: Record<string, string> | undefined;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [copied, setCopied] = useState(false);
  const [copiedSnippet, setCopiedSnippet] = useState(false);
  const pricingInfo = formatPricingLabel(tool.pricing_model);
  const verifiedBadgeText =
    tool.verified_badge || tool.verified_at ? "Verified" : null;

  const copyExamplePrompt = () => {
    if (!tool.prompt_style?.example) return;
    navigator.clipboard.writeText(tool.prompt_style.example);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const copySnippet = () => {
    if (!tool.api_snippet) return;
    navigator.clipboard.writeText(tool.api_snippet);
    setCopiedSnippet(true);
    setTimeout(() => setCopiedSnippet(false), 2000);
  };

  const formattedPricingChecked = tool.pricing_checked_at
    ? new Date(tool.pricing_checked_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[calc(100vw-2rem)] max-w-2xl max-h-[90vh] overflow-y-auto p-5 sm:p-7 rounded-2xl bg-card border-border shadow-2xl">
        {/* Wide OG Image Preview Banner at top of modal */}
        {tool.og_image_url && (
          <ToolPreviewBanner ogImageUrl={tool.og_image_url} name={tool.name} />
        )}

        {/* Modal Header */}
        <DialogHeader className="pb-5 border-b border-border/80 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <ToolLogo logoUrl={tool.logo_url} name={tool.name} className="size-12 rounded-xl" />
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <DialogTitle className="text-xl font-extrabold tracking-tight text-foreground">
                    {tool.name}
                  </DialogTitle>
                  {tool.is_pick && (
                    <Badge className="bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30 gap-1 text-[10px] font-semibold">
                      <Sparkles className="size-3 text-amber-500 fill-amber-500" />
                      <span>Pathwise Pick</span>
                    </Badge>
                  )}
                  {verifiedBadgeText && (
                    <Badge
                      variant="outline"
                      className="text-[10px] font-medium text-emerald-700 dark:text-emerald-400 border-emerald-500/30 bg-emerald-500/5 gap-1"
                    >
                      <ShieldCheck className="size-3 text-emerald-500" />
                      <span>{verifiedBadgeText}</span>
                    </Badge>
                  )}
                  {tool.ecosystem === "meta" && (
                    <Badge className="bg-sky-500/15 text-sky-700 dark:text-sky-300 border-sky-500/30 gap-1 text-[10px] font-semibold">
                      <span>Meta</span>
                    </Badge>
                  )}
                  {tool.ecosystem === "meta" && formatKindLabel(tool.kind) && (
                    <Badge
                      variant="outline"
                      className="text-[10px] font-medium text-muted-foreground border-border gap-1"
                    >
                      <span>{formatKindLabel(tool.kind)}</span>
                    </Badge>
                  )}
                  {tool.used_in_workflows_count != null && tool.used_in_workflows_count >= 10 && (
                    <Badge
                      variant="outline"
                      className="text-[10px] font-medium text-primary border-primary/30 bg-primary/5 gap-1"
                    >
                      <span>Used in {tool.used_in_workflows_count} workflows</span>
                    </Badge>
                  )}
                </div>
                {tool.tagline && (
                  <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                    {tool.tagline}
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {tool.docs_url && (
                <Button asChild size="sm" variant="outline" className="gap-1.5 shadow-xs">
                  <a href={tool.docs_url} target="_blank" rel="noopener noreferrer">
                    <span>Docs</span>
                    <ExternalLink className="size-3.5" />
                  </a>
                </Button>
              )}
              <Button asChild size="sm" variant="default" className="gap-1.5 shadow-xs">
                <a
                  href={`${getApiBaseUrl()}${tool.go_path || `/go/${tool.id}`}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <span>Open tool</span>
                  <ArrowUpRight className="size-4" />
                </a>
              </Button>
            </div>
          </div>
        </DialogHeader>

        {/* Modal Body */}
        <div className="space-y-6 pt-5">
          {/* Summary & How It Helps */}
          {(tool.summary || tool.how_it_helps) && (
            <div className="space-y-3">
              {tool.summary && (
                <div>
                  <h4 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground mb-1">
                    Summary
                  </h4>
                  <p className="text-sm text-foreground/90 leading-relaxed">{tool.summary}</p>
                </div>
              )}
              {tool.how_it_helps && (
                <div className="rounded-xl bg-muted/40 border border-border/60 p-3.5">
                  <h4 className="text-[11px] font-bold uppercase tracking-wider text-primary mb-1">
                    How it helps
                  </h4>
                  <p className="text-xs text-foreground/90 leading-relaxed">{tool.how_it_helps}</p>
                </div>
              )}
            </div>
          )}

          {/* Meta model details */}
          {tool.ecosystem === "meta" && (
            <div className="rounded-2xl border border-sky-500/25 bg-sky-500/5 p-5 space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2 text-sky-700 dark:text-sky-300 font-bold text-sm">
                  <Code2 className="size-4" />
                  <span>Meta model</span>
                </div>
                {tool.model_id && (
                  <code className="text-xs font-mono bg-background border border-border rounded-md px-2 py-1">
                    {tool.model_id}
                  </code>
                )}
              </div>

              {(Boolean(tool.jobs?.length) ||
                Boolean(tool.input_types?.length) ||
                Boolean(tool.output_types?.length)) && (
                <div>
                  <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-1.5">
                    Capabilities
                  </span>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {tool.jobs?.map((jobSlug) => {
                      const label =
                        jobLabels?.[jobSlug] || jobSlug.replace(/_/g, " ");
                      return (
                        <Badge
                          key={jobSlug}
                          variant="outline"
                          className="text-[10px] text-muted-foreground font-normal bg-background border-border"
                        >
                          {label}
                        </Badge>
                      );
                    })}
                    {tool.input_types && tool.input_types.length > 0 && (
                      <span className="text-[11px] text-muted-foreground">
                        <strong>In:</strong> {tool.input_types.join(", ")}
                      </span>
                    )}
                    {tool.output_types && tool.output_types.length > 0 && (
                      <span className="text-[11px] text-muted-foreground">
                        <strong>Out:</strong> {tool.output_types.join(", ")}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {tool.api_snippet && (
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] uppercase font-bold text-muted-foreground">
                      API snippet
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={copySnippet}
                      className="h-7 text-xs gap-1 text-sky-700 dark:text-sky-300 hover:text-sky-700 hover:dark:text-sky-300 hover:bg-sky-500/10"
                    >
                      {copiedSnippet ? (
                        <>
                          <Check className="size-3" />
                          <span>Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="size-3" />
                          <span>Copy snippet</span>
                        </>
                      )}
                    </Button>
                  </div>
                  <pre className="rounded-xl bg-background border border-border p-3.5 text-xs font-mono text-foreground overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                    {tool.api_snippet}
                  </pre>
                </div>
              )}

              {tool.sources && tool.sources.length > 0 && (
                <div>
                  <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-1.5">
                    Sources
                  </span>
                  <ul className="text-xs space-y-1">
                    {tool.sources.map((src, idx) => (
                      <li key={idx}>
                        <a
                          href={src.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline inline-flex items-center gap-1 break-all"
                        >
                          <span>{src.url}</span>
                          <ExternalLink className="size-3 shrink-0" />
                        </a>
                        {formatShortDate(src.fetched_at) && (
                          <span className="text-muted-foreground ml-1.5 text-[11px]">
                            ({formatShortDate(src.fetched_at)})
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {tool.verified_by && (
                <p className="text-[11px] text-muted-foreground pt-1 border-t border-border/50">
                  Verified by {tool.verified_by}
                </p>
              )}
            </div>
          )}

          {/* Pros and Cons */}
          {((tool.pros && tool.pros.length > 0) || (tool.cons && tool.cons.length > 0)) && (
            <div className="grid sm:grid-cols-2 gap-4">
              {tool.pros && tool.pros.length > 0 && (
                <div className="rounded-xl bg-emerald-500/5 border border-emerald-500/20 p-4 space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
                    <CheckCircle2 className="size-3.5" />
                    <span>Pros</span>
                  </h4>
                  <ul className="text-xs text-foreground/90 space-y-1.5">
                    {tool.pros.map((pro, idx) => (
                      <li key={idx} className="flex items-start gap-1.5">
                        <Check className="size-3.5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                        <span>{pro}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {tool.cons && tool.cons.length > 0 && (
                <div className="rounded-xl bg-amber-500/5 border border-amber-500/20 p-4 space-y-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-amber-700 dark:text-amber-300 flex items-center gap-1.5">
                    <AlertCircle className="size-3.5" />
                    <span>Cons & Limitations</span>
                  </h4>
                  <ul className="text-xs text-foreground/90 space-y-1.5">
                    {tool.cons.map((con, idx) => (
                      <li key={idx} className="flex items-start gap-1.5">
                        <span className="text-amber-600 dark:text-amber-400 shrink-0 font-bold">•</span>
                        <span>{con}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Pricing Details Breakdown (Only available fields) */}
          {(() => {
            const hasPricingModel = Boolean(tool.pricing_model && tool.pricing_model !== "unknown");
            const hasStartingPrice =
              tool.starting_price_monthly_usd != null || tool.pricing_model === "free";
            const hasFreeTier = tool.has_free_tier != null;
            const hasCreditCard = tool.credit_card_required != null;
            const hasCommercial = tool.commercial_use_on_free != null;
            const hasWatermark = tool.watermark_on_free != null;
            const hasSkillLevel = Boolean(tool.skill_level);
            const hasAnyGridItem =
              hasStartingPrice ||
              hasFreeTier ||
              hasCreditCard ||
              hasCommercial ||
              hasWatermark ||
              hasSkillLevel;
            const hasAnyPricingContent =
              hasPricingModel ||
              hasAnyGridItem ||
              Boolean(tool.free_tier_limits) ||
              Boolean(tool.pricing_notes) ||
              Boolean(tool.pricing_url);

            if (!hasAnyPricingContent) return null;

            return (
              <div className="rounded-xl border border-border bg-card p-4 space-y-3.5">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-foreground">
                    Pricing & Monetization
                  </h4>
                  {hasPricingModel && pricingInfo && (
                    <Badge
                      variant="outline"
                      className={cn("text-xs font-semibold", pricingInfo.className)}
                    >
                      {pricingInfo.label}
                    </Badge>
                  )}
                </div>

                {hasAnyGridItem && (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                    {hasStartingPrice && (
                      <div className="rounded-lg bg-muted/40 p-2.5">
                        <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
                          Starting Price
                        </span>
                        <span className="font-bold text-foreground">
                          {tool.starting_price_monthly_usd != null
                            ? `$${tool.starting_price_monthly_usd}/mo`
                            : "Free"}
                        </span>
                      </div>
                    )}

                    {hasFreeTier && (
                      <div className="rounded-lg bg-muted/40 p-2.5">
                        <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
                          Free Tier
                        </span>
                        <span className="font-bold text-foreground">
                          {tool.has_free_tier ? "Available" : "No free tier"}
                        </span>
                      </div>
                    )}

                    {hasCreditCard && (
                      <div className="rounded-lg bg-muted/40 p-2.5">
                        <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
                          Credit Card Required
                        </span>
                        <span className="font-bold text-foreground">
                          {tool.credit_card_required ? "Yes" : "No"}
                        </span>
                      </div>
                    )}

                    {hasCommercial && (
                      <div className="rounded-lg bg-muted/40 p-2.5">
                        <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
                          Commercial on Free
                        </span>
                        <span className="font-bold text-foreground">
                          {tool.commercial_use_on_free ? "Allowed" : "Personal only"}
                        </span>
                      </div>
                    )}

                    {hasWatermark && (
                      <div className="rounded-lg bg-muted/40 p-2.5">
                        <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
                          Watermark on Free
                        </span>
                        <span className="font-bold text-foreground">
                          {tool.watermark_on_free ? "Yes" : "No watermark"}
                        </span>
                      </div>
                    )}

                    {hasSkillLevel && (
                      <div className="rounded-lg bg-muted/40 p-2.5">
                        <span className="text-muted-foreground block text-[10px] uppercase font-semibold">
                          Skill Level
                        </span>
                        <span className="font-bold text-foreground capitalize">
                          {tool.skill_level}
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {/* Free Tier Limits */}
                {tool.free_tier_limits && (
                  <div className="text-xs text-foreground/90 bg-muted/20 rounded-lg p-2.5">
                    <span className="font-semibold text-muted-foreground block text-[10px] uppercase mb-0.5">
                      Free-tier limits
                    </span>
                    <span>{tool.free_tier_limits}</span>
                  </div>
                )}

                {/* Pricing notes */}
                {tool.pricing_notes && (
                  <p className="text-xs text-muted-foreground leading-relaxed italic">
                    {tool.pricing_notes}
                  </p>
                )}

                {/* Checked at & pricing URL */}
                {(formattedPricingChecked || tool.pricing_url) && (
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1 border-t border-border/50">
                    {formattedPricingChecked && <span>Checked on {formattedPricingChecked}</span>}
                    {tool.pricing_url && (
                      <a
                        href={tool.pricing_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline inline-flex items-center gap-1 ml-auto"
                      >
                        <span>Official pricing page</span>
                        <ExternalLink className="size-3" />
                      </a>
                    )}
                  </div>
                )}
              </div>
            );
          })()}

          {/* Platforms & Skill Level */}
          {tool.platforms && tool.platforms.length > 0 && (
            <div>
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground mb-2">
                Supported Platforms
              </h4>
              <div className="flex flex-wrap gap-2">
                {tool.platforms.map((plat) => (
                  <Badge
                    key={plat}
                    variant="secondary"
                    className="text-xs uppercase font-medium"
                  >
                    {plat}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Best For / Not For */}
          {(tool.best_for || tool.not_for) && (
            <div className="grid sm:grid-cols-2 gap-4">
              {tool.best_for && (
                <div className="rounded-xl bg-muted/30 border border-border/60 p-3.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-primary block mb-1">
                    Best For
                  </span>
                  <p className="text-xs text-foreground/90">{tool.best_for}</p>
                </div>
              )}
              {tool.not_for && (
                <div className="rounded-xl bg-muted/30 border border-border/60 p-3.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block mb-1">
                    Not Recommended For
                  </span>
                  <p className="text-xs text-foreground/90">{tool.not_for}</p>
                </div>
              )}
            </div>
          )}

          {/* Prompt Engineering Guidelines & Copy Example Prompt */}
          {tool.prompt_style && (tool.prompt_style.technique || tool.prompt_style.example) && (
            <div className="rounded-2xl border border-primary/20 bg-primary/5 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-primary font-bold text-sm">
                  <Code2 className="size-4" />
                  <span>Prompt Style & Engineering</span>
                </div>
                {tool.prompt_style.format && (
                  <Badge variant="outline" className="text-xs border-primary/30 text-primary">
                    Format: {tool.prompt_style.format}
                  </Badge>
                )}
              </div>

              {tool.prompt_style.technique && (
                <div>
                  <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-0.5">
                    Technique
                  </span>
                  <p className="text-xs font-semibold text-foreground">
                    {tool.prompt_style.technique}
                  </p>
                </div>
              )}

              {tool.prompt_style.rules && tool.prompt_style.rules.length > 0 && (
                <div>
                  <span className="text-[10px] uppercase font-bold text-muted-foreground block mb-1">
                    Formatting Rules
                  </span>
                  <ul className="text-xs text-foreground/90 space-y-1 list-disc pl-4">
                    {tool.prompt_style.rules.map((rule, idx) => (
                      <li key={idx}>{rule}</li>
                    ))}
                  </ul>
                </div>
              )}

              {tool.prompt_style.example && (
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] uppercase font-bold text-muted-foreground">
                      Example Prompt
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={copyExamplePrompt}
                      className="h-7 text-xs gap-1 text-primary hover:text-primary hover:bg-primary/10"
                    >
                      {copied ? (
                        <>
                          <Check className="size-3" />
                          <span>Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy className="size-3" />
                          <span>Copy Example Prompt</span>
                        </>
                      )}
                    </Button>
                  </div>
                  <pre className="rounded-xl bg-background border border-border p-3.5 text-xs font-mono text-foreground overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                    {tool.prompt_style.example}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* I/O Types & Official Documentation */}
          {(Boolean(tool.input_types?.length) ||
            Boolean(tool.output_types?.length) ||
            Boolean(tool.docs_url)) && (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-muted-foreground border-t border-border pt-4">
              <div className="flex items-center gap-4 flex-wrap">
                {tool.input_types && tool.input_types.length > 0 && (
                  <span>
                    <strong>Inputs:</strong> {tool.input_types.join(", ")}
                  </span>
                )}
                {tool.output_types && tool.output_types.length > 0 && (
                  <span>
                    <strong>Outputs:</strong> {tool.output_types.join(", ")}
                  </span>
                )}
              </div>

              {tool.docs_url && (
                <a
                  href={tool.docs_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline inline-flex items-center gap-1 shrink-0"
                >
                  <span>Documentation</span>
                  <ExternalLink className="size-3" />
                </a>
              )}
            </div>
          )}

        </div>
      </DialogContent>
    </Dialog>
  );
}
