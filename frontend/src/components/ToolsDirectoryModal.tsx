import React, { useEffect, useState, useMemo } from "react";
import {
  Compass,
  Search,
  ExternalLink,
  Sparkles,
  ShieldCheck,
  Loader2,
  ArrowRight,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { api, getApiBaseUrl, ToolResponse, TaxonomyPayload } from "@/lib/api";
import { cn } from "@/lib/utils";

const FALLBACK_DOMAINS = [
  { id: "all", label: "All Domains" },
  { id: "software", label: "Software" },
  { id: "builders", label: "Builders" },
  { id: "design", label: "Design" },
  { id: "video", label: "Video" },
  { id: "audio", label: "Audio" },
  { id: "writing", label: "Writing" },
  { id: "research", label: "Research" },
  { id: "deploy_backend", label: "Deploy & Cloud" },
  { id: "freelance_ops", label: "Freelance Ops" },
];

function formatVerifiedBadge(dateStr?: string | null): string | null {
  if (!dateStr) return null;
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return null;
    const month = d.toLocaleString("en-US", { month: "short" });
    const year = d.getFullYear();
    return `Verified ${month} ${year}`;
  } catch {
    return null;
  }
}

export function ToolsDirectoryModal() {
  const [open, setOpen] = useState(false);
  const [tools, setTools] = useState<ToolResponse[]>([]);
  const [taxonomy, setTaxonomy] = useState<TaxonomyPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedDomain, setSelectedDomain] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  const loadData = async () => {
    setLoading(true);
    try {
      const [toolsData, taxData] = await Promise.all([
        api.getTools(),
        api.getTaxonomy().catch(() => null),
      ]);
      setTools(toolsData);
      if (taxData) setTaxonomy(taxData);
    } catch (err) {
      console.error("Failed to load tools catalog", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadData();
    }
  }, [open]);

  const domainTabs = useMemo(() => {
    if (taxonomy?.domains?.length) {
      return [
        { id: "all", label: "All Domains" },
        ...taxonomy.domains.map((d) => ({ id: d.slug, label: d.label })),
      ];
    }
    return FALLBACK_DOMAINS;
  }, [taxonomy]);

  const filteredTools = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    const filtered = tools.filter((tool) => {
      if (selectedDomain !== "all") {
        const d = (tool.domain || tool.category || "").toLowerCase();
        if (d !== selectedDomain.toLowerCase()) return false;
      }
      if (!q) return true;
      return (
        tool.name.toLowerCase().includes(q) ||
        Boolean(tool.tagline?.toLowerCase().includes(q)) ||
        Boolean(tool.summary?.toLowerCase().includes(q)) ||
        tool.jobs?.some((j) => j.toLowerCase().includes(q))
      );
    });

    // Pathwise picks first, then name
    return filtered.sort((a, b) => {
      const aPick = a.is_pick ? 1 : 0;
      const bPick = b.is_pick ? 1 : 0;
      if (bPick !== aPick) return bPick - aPick;
      return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
    });
  }, [tools, selectedDomain, searchQuery]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button type="button" className="nav-link cursor-pointer">
          Discover
        </button>
      </DialogTrigger>

      <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col bg-card">
        <DialogHeader>
          <div className="flex items-center justify-between pr-6">
            <div className="flex items-center gap-3">
              <span className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
                <Compass className="size-5" />
              </span>
              <div>
                <DialogTitle className="text-xl font-bold">Verified Tools Catalog</DialogTitle>
                <DialogDescription className="text-xs">
                  Real creative tools across 9 domains with verified prompt styles and pricing models.
                </DialogDescription>
              </div>
            </div>

            <Button asChild variant="outline" size="sm" className="hidden sm:inline-flex text-xs gap-1.5">
              <Link to="/tools" onClick={() => setOpen(false)}>
                <span>Full Directory</span>
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </div>
        </DialogHeader>

        {/* Filters & Search */}
        <div className="mt-2 space-y-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search tools by name, tagline, or job slug..."
                className="h-9 pl-9 text-xs bg-background"
              />
            </div>
          </div>

          {/* Domain Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
            {domainTabs.map((tab) => (
              <Button
                key={tab.id}
                type="button"
                variant={selectedDomain === tab.id ? "default" : "outline"}
                size="sm"
                onClick={() => setSelectedDomain(tab.id)}
                className={cn(
                  "h-7 rounded-md text-xs px-2.5 shrink-0 whitespace-nowrap",
                  selectedDomain === tab.id ? "shadow-xs" : "bg-background text-muted-foreground"
                )}
              >
                {tab.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Tools Grid */}
        <div className="mt-4 flex-1 overflow-y-auto pr-1">
          {loading ? (
            <div className="flex h-48 items-center justify-center">
              <Loader2 className="size-6 animate-spin text-primary" />
            </div>
          ) : filteredTools.length === 0 ? (
            <div className="flex h-48 flex-col items-center justify-center text-center text-xs text-muted-foreground">
              <p>No verified tools found matching your query.</p>
              <Button
                variant="link"
                size="sm"
                onClick={() => {
                  setSearchQuery("");
                  setSelectedDomain("all");
                }}
                className="text-xs mt-1"
              >
                Reset filters
              </Button>
            </div>
          ) : (
            <div className="grid gap-3.5 sm:grid-cols-2">
              {filteredTools.map((tool) => {
                const verifiedBadge = tool.verified_badge || formatVerifiedBadge(tool.verified_at);
                return (
                  <div
                    key={tool.id}
                    className="flex flex-col justify-between rounded-xl border border-border bg-background p-4 transition-all hover:border-primary/50 hover:shadow-xs"
                  >
                    <div>
                      {/* Top Badges */}
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {tool.is_pick && (
                            <Badge className="bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30 gap-1 text-[10px] font-semibold py-0.5">
                              <Sparkles className="size-3 text-amber-500 fill-amber-500" />
                              <span>Pick</span>
                            </Badge>
                          )}
                          {verifiedBadge && (
                            <Badge
                              variant="outline"
                              className="text-[10px] text-emerald-700 dark:text-emerald-400 border-emerald-500/30 bg-emerald-500/5 gap-1 py-0.5"
                            >
                              <ShieldCheck className="size-3 text-emerald-500" />
                              <span>{verifiedBadge}</span>
                            </Badge>
                          )}
                        </div>
                        <Badge variant="outline" className="text-[10px] uppercase font-semibold">
                          {tool.pricing_model || tool.pricing || "freemium"}
                        </Badge>
                      </div>

                      {/* Title + Open Link */}
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <h4 className="font-bold text-sm text-foreground truncate">{tool.name}</h4>
                          {tool.domain && (
                            <span className="text-[10px] text-muted-foreground capitalize">
                              {tool.domain.replace("_", " ")}
                            </span>
                          )}
                        </div>
                        <a
                          href={`${getApiBaseUrl()}${tool.go_path || `/go/${tool.id}`}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground shrink-0"
                          aria-label={`Open ${tool.name}`}
                        >
                          <ExternalLink className="size-4" />
                        </a>
                      </div>

                      {/* Tagline / Free Tier Summary */}
                      <p className="mt-2 text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                        {tool.tagline || tool.summary || tool.best_for || (tool.domain ? `AI tool for ${tool.domain.replace(/_/g, " ")}` : "Verified AI tool")}
                      </p>

                      {tool.has_free_tier && tool.free_tier_summary && (
                        <div className="mt-2 rounded bg-emerald-500/5 border border-emerald-500/15 px-2 py-1 text-[10px] text-emerald-800 dark:text-emerald-300">
                          <span className="font-semibold">Free: </span>
                          <span className="line-clamp-1">{tool.free_tier_summary}</span>
                        </div>
                      )}

                      {/* Jobs chips */}
                      {tool.jobs && tool.jobs.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-1">
                          {tool.jobs.slice(0, 3).map((job, idx) => (
                            <span
                              key={idx}
                              className="rounded bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground font-mono"
                            >
                              {job.replace(/_/g, " ")}
                            </span>
                          ))}
                          {tool.jobs.length > 3 && (
                            <span className="text-[10px] text-muted-foreground font-mono px-1">
                              +{tool.jobs.length - 3}
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="mt-3 border-t border-border pt-2 flex items-center justify-between text-[10px] text-muted-foreground">
                      <span>May include affiliate link</span>
                      <Link
                        to="/tools"
                        onClick={() => setOpen(false)}
                        className="text-primary hover:underline flex items-center gap-1 font-medium"
                      >
                        <span>Details</span>
                        <ArrowRight className="size-3" />
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
