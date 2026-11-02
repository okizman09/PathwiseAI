import { createFileRoute, redirect } from "@tanstack/react-router";
import {
  Loader2,
  Trash2,
  ExternalLink,
  Link2,
  Sparkles,
  Check,
  RefreshCw,
  Edit3,
  CheckCircle2,
  XCircle,
  AlertCircle,
  AlertTriangle,
  Globe,
  BookOpen,
  FileCode,
  ShieldCheck,
  UploadCloud,
  Star,
  Clock,
  CheckCheck,
  Activity,
  Layers,
  BarChart3,
} from "lucide-react";
import { useEffect, useState, useRef, type FormEvent } from "react";

import { AppHeader } from "@/components/AppHeader";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  api,
  type ToolResponse,
  type ToolPromptStyle,
  type ToolEvidenceItem,
  type CardImportResponse,
  type ToolMetricResponse,
} from "@/lib/api";
import { supabase } from "@/lib/supabase";

export const Route = createFileRoute("/admin")({
  ssr: false,
  beforeLoad: async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) throw redirect({ to: "/login" });
    const me = await api.getMe().catch(() => null);
    if (!me || me.role !== "admin") throw redirect({ to: "/app" });
  },
  head: () => ({
    meta: [
      { title: "Tool catalog admin — Pathwise" },
      { name: "description", content: "Manage the Pathwise tool catalog, prompt styles, and monetization links." },
      { property: "og:title", content: "Tool catalog admin — Pathwise" },
      { property: "og:description", content: "Manage the Pathwise tool catalog, prompt styles, and monetization links." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminPage,
});

const errMsg = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");

const TAXONOMY_DOMAINS = [
  "software",
  "builders",
  "design",
  "video",
  "audio",
  "writing",
  "research",
  "deploy_backend",
  "freelance_ops",
];

interface EditFormData {
  name: string;
  domain: string;
  category: string;
  official_domains: string;
  url: string;
  pricing_url: string;
  affiliate_url: string;
  docs_url: string;
  logo_url: string;
  logo_source: string;
  pricing_model: string;
  has_free_tier: boolean | null;
  free_tier_summary: string;
  free_tier_limits: string;
  starting_price_monthly_usd: string;
  pricing_notes: string;
  credit_card_required: boolean | null;
  watermark_on_free: boolean | null;
  commercial_use_on_free: boolean | null;
  skill_level: string;
  platformsText: string;
  jobsText: string;
  tagline: string;
  summary: string;
  how_it_helps: string;
  prosText: string;
  consText: string;
  best_for: string;
  not_for: string;
  technique: string;
  format: string;
  rulesText: string;
  example: string;
  is_pick: boolean;
  status: "draft" | "researched" | "verified" | "hidden";
  review_flags: string[];
}

function AdminPage() {
  const [session, setSession] = useState<{ id: any; email: string; role: string; access_token: string } | null>(null);

  useEffect(() => {
    api.getMe().then((me) => {
      setSession({ ...me, access_token: "" });
    }).catch((e) => {
      console.error(e);
      window.location.href = "/login";
    });
  }, []);

  const [tools, setTools] = useState<ToolResponse[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Tab & import state
  const [adminTab, setAdminTab] = useState<"catalog" | "import" | "metrics">("catalog");
  const [importJson, setImportJson] = useState("");
  const [importing, setImporting] = useState(false);
  const [importResponse, setImportResponse] = useState<CardImportResponse | null>(null);
  const [importError, setImportError] = useState("");

  // Usage signals / metrics state (Slice C7)
  const [metrics, setMetrics] = useState<ToolMetricResponse[]>([]);
  const [loadingMetrics, setLoadingMetrics] = useState(false);

  async function loadMetrics() {
    setLoadingMetrics(true);
    try {
      const data = await api.getAdminToolMetrics();
      setMetrics(data);
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setLoadingMetrics(false);
    }
  }

  // Link check cron state
  const [checkingLinks, setCheckingLinks] = useState(false);

  // Edit affiliate URL inline state
  const [editingAffiliateId, setEditingAffiliateId] = useState<number | null>(null);
  const [affiliateInput, setAffiliateInput] = useState("");

  // Drawer review/edit state
  const [selectedTool, setSelectedTool] = useState<ToolResponse | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [savingDrawer, setSavingDrawer] = useState(false);

  // Fresh JSON recheck state
  const [freshCardJson, setFreshCardJson] = useState("");
  const [freshDiff, setFreshDiff] = useState<Record<string, { current: any; new: any }> | null>(null);
  const [freshLoading, setFreshLoading] = useState(false);
  const [freshError, setFreshError] = useState("");

  // Logo pipeline state
  const [logoActionLoading, setLogoActionLoading] = useState(false);
  const [pasteUrlInput, setPasteUrlInput] = useState("");
  const [showPasteUrl, setShowPasteUrl] = useState(false);
  const [logoMessage, setLogoMessage] = useState<{ text: string; error?: boolean } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [formData, setFormData] = useState<EditFormData>({
    name: "",
    domain: "software",
    category: "software",
    official_domains: "",
    url: "",
    pricing_url: "",
    affiliate_url: "",
    docs_url: "",
    logo_url: "",
    logo_source: "",
    pricing_model: "freemium",
    has_free_tier: null,
    free_tier_summary: "",
    free_tier_limits: "",
    starting_price_monthly_usd: "",
    pricing_notes: "",
    credit_card_required: null,
    watermark_on_free: null,
    commercial_use_on_free: null,
    skill_level: "all",
    platformsText: "",
    jobsText: "",
    tagline: "",
    summary: "",
    how_it_helps: "",
    prosText: "",
    consText: "",
    best_for: "",
    not_for: "",
    technique: "",
    format: "",
    rulesText: "",
    example: "",
    is_pick: false,
    status: "draft",
    review_flags: [],
  });

  async function load() {
    setLoading(true);
    setError("");
    try {
      if (statusFilter === "stale") {
        setTools(await api.getAdminStaleTools());
      } else {
        setTools(await api.getAdminTools(statusFilter || undefined));
      }
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function handleCheckAllLinks() {
    setCheckingLinks(true);
    setError("");
    setSuccess("");
    try {
      const res = await api.checkAllAdminLinks();
      setSuccess(
        `Link health check complete: ${res.checked} checked, ${res.ok} OK, ${res.dead} dead (marked hidden).`
      );
      await load();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setCheckingLinks(false);
    }
  }

  async function handleFetchLogo() {
    if (!selectedTool) return;
    setLogoActionLoading(true);
    setLogoMessage(null);
    try {
      const updated = await api.fetchToolLogo(selectedTool.id);
      setFormData((prev) => ({
        ...prev,
        logo_url: updated.logo_url || "",
        logo_source: updated.logo_source || "",
      }));
      setSelectedTool(updated);
      setLogoMessage({ text: `Logo fetched successfully (${updated.logo_source || "none"}).` });
      await load();
    } catch (e: any) {
      setLogoMessage({ text: errMsg(e), error: true });
    } finally {
      setLogoActionLoading(false);
    }
  }

  async function handlePasteLogoUrl() {
    if (!selectedTool || !pasteUrlInput.trim()) return;
    setLogoActionLoading(true);
    setLogoMessage(null);
    try {
      const updated = await api.pasteToolLogoUrl(selectedTool.id, pasteUrlInput.trim());
      setFormData((prev) => ({
        ...prev,
        logo_url: updated.logo_url || "",
        logo_source: updated.logo_source || "manual",
      }));
      setSelectedTool(updated);
      setPasteUrlInput("");
      setShowPasteUrl(false);
      setLogoMessage({ text: "Logo downloaded and stored (source: manual)." });
      await load();
    } catch (e: any) {
      setLogoMessage({ text: errMsg(e), error: true });
    } finally {
      setLogoActionLoading(false);
    }
  }

  async function handleUploadLogo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !selectedTool) return;
    if (file.size > 1024 * 1024) {
      setLogoMessage({ text: "File exceeds 1 MB limit.", error: true });
      return;
    }
    setLogoActionLoading(true);
    setLogoMessage(null);
    try {
      const updated = await api.uploadToolLogo(selectedTool.id, file);
      setFormData((prev) => ({
        ...prev,
        logo_url: updated.logo_url || "",
        logo_source: updated.logo_source || "manual",
      }));
      setSelectedTool(updated);
      setLogoMessage({ text: "Logo uploaded and stored (source: manual)." });
      await load();
    } catch (e: any) {
      setLogoMessage({ text: errMsg(e), error: true });
    } finally {
      setLogoActionLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function openReviewDrawer(tool: ToolResponse) {
    setSelectedTool(tool);
    setFreshDiff(null);
    setFreshCardJson("");
    setFreshError("");
    setLogoMessage(null);
    setShowPasteUrl(false);
    setPasteUrlInput("");
    setFormData({
      name: tool.name || "",
      domain: tool.domain || tool.category || "software",
      category: tool.category || tool.domain || "software",
      official_domains: (tool.official_domains || []).join(", "),
      url: tool.url || "",
      pricing_url: tool.pricing_url || "",
      affiliate_url: tool.affiliate_url || "",
      docs_url: tool.docs_url || "",
      logo_url: tool.logo_url || "",
      logo_source: tool.logo_source || "",
      pricing_model: tool.pricing_model || "freemium",
      has_free_tier: tool.has_free_tier ?? null,
      free_tier_summary: tool.free_tier_summary || "",
      free_tier_limits: tool.free_tier_limits || "",
      starting_price_monthly_usd:
        tool.starting_price_monthly_usd != null ? String(tool.starting_price_monthly_usd) : "",
      pricing_notes: tool.pricing_notes || "",
      credit_card_required: tool.credit_card_required ?? null,
      watermark_on_free: tool.watermark_on_free ?? null,
      commercial_use_on_free: tool.commercial_use_on_free ?? null,
      skill_level: tool.skill_level || "all",
      platformsText: (tool.platforms || []).join(", "),
      jobsText: (tool.jobs || []).join(", "),
      tagline: tool.tagline || "",
      summary: tool.summary || "",
      how_it_helps: tool.how_it_helps || "",
      prosText: (tool.pros || []).join("\n"),
      consText: (tool.cons || []).join("\n"),
      best_for: tool.best_for || "",
      not_for: tool.not_for || "",
      technique: tool.prompt_style?.technique || "",
      format: tool.prompt_style?.format || "",
      rulesText: (tool.prompt_style?.rules || []).join("\n"),
      example: tool.prompt_style?.example || "",
      is_pick: Boolean(tool.is_pick),
      status: (tool.status as any) || "draft",
      review_flags: tool.review_flags ? [...tool.review_flags] : [],
    });
    setDrawerOpen(true);
  }

  async function handleImportCards(e?: FormEvent) {
    if (e) e.preventDefault();
    if (!importJson.trim()) return;
    setImporting(true);
    setImportError("");
    setImportResponse(null);
    try {
      const parsed = JSON.parse(importJson.trim());
      const cards = Array.isArray(parsed) ? parsed : parsed.cards;
      if (!Array.isArray(cards)) {
        throw new Error("JSON must be an array of tool cards or contain a 'cards' array.");
      }
      const res = await api.importCards(cards);
      setImportResponse(res);
      setSuccess(`Import finished: ${res.created} created, ${res.updated} updated, ${res.rejected} rejected.`);
      await load();
    } catch (err) {
      setImportError(errMsg(err));
    } finally {
      setImporting(false);
    }
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (content) setImportJson(content);
    };
    reader.readAsText(file);
  }

  async function handleCalculateDiff() {
    if (!selectedTool || !freshCardJson.trim()) return;
    setFreshLoading(true);
    setFreshError("");
    setFreshDiff(null);
    try {
      const parsed = JSON.parse(freshCardJson.trim());
      const cardData = Array.isArray(parsed) ? parsed[0] : (parsed.cards ? parsed.cards[0] : parsed);
      const res = await api.recheckAdminTool(selectedTool.id, cardData, false);
      setFreshDiff(res.diff || {});
    } catch (e) {
      setFreshError(errMsg(e));
    } finally {
      setFreshLoading(false);
    }
  }

  async function handleApplyFreshCard() {
    if (!selectedTool || !freshCardJson.trim()) return;
    setFreshLoading(true);
    setFreshError("");
    try {
      const parsed = JSON.parse(freshCardJson.trim());
      const cardData = Array.isArray(parsed) ? parsed[0] : (parsed.cards ? parsed.cards[0] : parsed);
      await api.recheckAdminTool(selectedTool.id, cardData, true);
      setSuccess(`Fresh card applied successfully for ${selectedTool.name}!`);
      setFreshDiff(null);
      setFreshCardJson("");
      await load();
      const updatedTool = await api.getAdminTools().then((ts) => ts.find((t) => t.id === selectedTool.id));
      if (updatedTool) openReviewDrawer(updatedTool);
    } catch (e) {
      setFreshError(errMsg(e));
    } finally {
      setFreshLoading(false);
    }
  }

  // 8 Verification Rules Checklist
  const validationChecks = [
    {
      id: "domain",
      label: "Domain set to valid taxonomy domain",
      passed: TAXONOMY_DOMAINS.includes(formData.domain),
    },
    {
      id: "jobs",
      label: "At least one valid taxonomy job slug defined",
      passed: formData.jobsText.split(",").map((j) => j.trim()).filter(Boolean).length > 0,
    },
    {
      id: "pricing_model",
      label: "Pricing model set (not unknown)",
      passed: Boolean(formData.pricing_model && formData.pricing_model !== "unknown"),
    },
    {
      id: "free_tier",
      label: "Free-tier fields set (for free / freemium / free_trial)",
      passed:
        !["free", "freemium", "free_trial"].includes(formData.pricing_model) ||
        (formData.has_free_tier !== null &&
          (!formData.has_free_tier || Boolean(formData.free_tier_summary.trim()))),
    },
    {
      id: "evidence",
      label: "Every pricing field has evidence quote and source link",
      passed: Boolean(
        selectedTool?.evidence?.pricing_model?.source_url &&
          selectedTool?.evidence?.pricing_model?.quote
      ),
    },
    {
      id: "explanations",
      label: "Explanation limits met (tagline ≤ 90 chars, free tier ≤ 140 chars, 3 pros, 3 cons)",
      passed:
        Boolean(formData.tagline.trim()) &&
        formData.tagline.length <= 90 &&
        formData.free_tier_summary.length <= 140 &&
        formData.prosText.split("\n").map((p) => p.trim()).filter(Boolean).length === 3 &&
        formData.consText.split("\n").map((c) => c.trim()).filter(Boolean).length === 3,
    },
    {
      id: "link",
      label: "Primary link reachable (link_status is OK)",
      passed: selectedTool?.link_status === "ok",
    },
    {
      id: "flags",
      label: "All review flags marked reviewed (0 remaining)",
      passed: formData.review_flags.length === 0,
    },
  ];
  const allRulesPassed = validationChecks.every((c) => c.passed);
  const failedRules = validationChecks.filter((c) => !c.passed);

  function renderEvidenceBlock(label: string, evItem: ToolEvidenceItem | null | undefined) {
    if (!evItem) {
      return (
        <div className="mt-1 rounded border border-border/40 bg-muted/20 p-2 text-[11px] text-muted-foreground italic flex items-center justify-between">
          <span>No evidence quote recorded for {label}</span>
          <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground font-medium">
            <span className="size-1.5 rounded-full bg-muted-foreground/60"></span> Missing
          </span>
        </div>
      );
    }
    const isMatch = evItem.checked === true || evItem.checked === "ok" || evItem.checked === "match";
    const isMismatch = evItem.checked === false || evItem.checked === "mismatch" || evItem.checked === "fail";
    return (
      <div
        className={`mt-1.5 rounded-lg border p-2.5 text-xs ${
          isMismatch
            ? "border-rose-500/30 bg-rose-500/5 text-rose-900 dark:text-rose-200"
            : isMatch
            ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-900 dark:text-emerald-200"
            : "border-border/60 bg-muted/30 text-muted-foreground"
        }`}
      >
        <div className="flex items-center justify-between gap-2 pb-1 border-b border-border/30">
          <div className="flex items-center gap-1.5 font-mono text-[11px] truncate">
            <Link2 className="size-3 shrink-0" />
            <a
              href={evItem.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:underline text-primary truncate max-w-[280px]"
              title={evItem.source_url}
            >
              {evItem.source_url}
            </a>
          </div>
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider shrink-0 ${
              isMismatch
                ? "bg-rose-500/20 text-rose-600 dark:text-rose-400"
                : isMatch
                ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                : "bg-muted text-muted-foreground"
            }`}
          >
            <span
              className={`size-1.5 rounded-full ${
                isMismatch ? "bg-rose-500" : isMatch ? "bg-emerald-500" : "bg-muted-foreground"
              }`}
            />
            {isMismatch ? "Mismatch" : isMatch ? "Verified" : "Unchecked"}
          </span>
        </div>
        <p className="mt-1.5 text-[11px] italic font-sans text-foreground/80 line-clamp-3">
          "{evItem.quote}"
        </p>
      </div>
    );
  }

  async function handleDrawerSave(e?: FormEvent, targetStatus?: "draft" | "verified" | "hidden") {
    if (e) e.preventDefault();
    if (!selectedTool) return;
    setSavingDrawer(true);
    setError("");
    setSuccess("");

    try {
      const jobsArray = formData.jobsText
        .split(",")
        .map((j) => j.trim())
        .filter(Boolean);

      const rulesArray = formData.rulesText
        .split("\n")
        .map((r) => r.trim())
        .filter(Boolean);

      const promptStyle: ToolPromptStyle = {
        technique: formData.technique.trim(),
        format: formData.format.trim(),
        rules: rulesArray,
        example: formData.example.trim(),
      };

      const officialDomainsArray = formData.official_domains
        .split(",")
        .map((d) => d.trim())
        .filter(Boolean);

      const platformsArray = formData.platformsText
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);

      const prosArray = formData.prosText
        .split("\n")
        .map((p) => p.trim())
        .filter(Boolean);

      const consArray = formData.consText
        .split("\n")
        .map((c) => c.trim())
        .filter(Boolean);

      const updated = await api.updateAdminTool(selectedTool.id, {
        name: formData.name.trim(),
        domain: formData.domain.trim(),
        category: formData.domain.trim(),
        official_domains: officialDomainsArray,
        url: formData.url.trim(),
        pricing_url: formData.pricing_url.trim() || null,
        affiliate_url: formData.affiliate_url.trim() || null,
        docs_url: formData.docs_url.trim() || null,
        logo_url: formData.logo_url.trim() || null,
        logo_source: formData.logo_source.trim() || null,
        pricing_model: formData.pricing_model,
        has_free_tier: formData.has_free_tier,
        free_tier_summary: formData.free_tier_summary.trim() || null,
        free_tier_limits: formData.free_tier_limits.trim() || null,
        starting_price_monthly_usd: formData.starting_price_monthly_usd
          ? Number(formData.starting_price_monthly_usd)
          : null,
        pricing_notes: formData.pricing_notes.trim() || null,
        credit_card_required: formData.credit_card_required,
        watermark_on_free: formData.watermark_on_free,
        commercial_use_on_free: formData.commercial_use_on_free,
        skill_level: formData.skill_level,
        platforms: platformsArray,
        jobs: jobsArray,
        tagline: formData.tagline.trim(),
        summary: formData.summary.trim() || null,
        how_it_helps: formData.how_it_helps.trim() || null,
        pros: prosArray,
        cons: consArray,
        best_for: formData.best_for.trim(),
        not_for: formData.not_for.trim(),
        is_pick: formData.is_pick,
        status: targetStatus || (formData.status as any),
        review_flags: formData.review_flags,
        prompt_style: promptStyle,
        sources: selectedTool.sources ?? [],
        research_notes: selectedTool.research_notes ?? null,
      });

      setSuccess(`Updated tool card for "${updated.name}" successfully.`);
      setDrawerOpen(false);
      setSelectedTool(null);
      await load();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setSavingDrawer(false);
    }
  }

  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    const name = String(fd.get("name") ?? "").trim();
    if (!name) return;
    setAdding(true);
    setError("");
    setSuccess("");
    try {
      await api.createAdminTool({
        name,
        docs_url: String(fd.get("docs_url") ?? "").trim() || undefined,
        url: String(fd.get("url") ?? "").trim() || undefined,
        affiliate_url: String(fd.get("affiliate_url") ?? "").trim() || undefined,
      });
      form.reset();
      setSuccess(`Tool "${name}" created successfully.`);
      await load();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setAdding(false);
    }
  }

  async function run(fn: () => Promise<unknown>, successMsg?: string) {
    setError("");
    setSuccess("");
    try {
      await fn();
      if (successMsg) setSuccess(successMsg);
      await load();
    } catch (e) {
      setError(errMsg(e));
    }
  }

  async function saveAffiliateUrl(toolId: number) {
    await run(
      () => api.updateAdminTool(toolId, { affiliate_url: affiliateInput.trim() || null }),
      "Affiliate URL updated."
    );
    setEditingAffiliateId(null);
    setAffiliateInput("");
  }

  if (!session) return <div className="p-8 text-center text-muted-foreground">Loading session...</div>;

  return (
    <div className="min-h-screen bg-background">
      {session && <AppHeader session={session as any} />}
      <main className="mx-auto max-w-[1360px] px-5 py-12 sm:px-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <p className="eyebrow">Admin Console</p>
              <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-medium text-primary">
                <ShieldCheck className="size-3" /> Authenticated as {session.email}
              </span>
            </div>
            <h1 className="mt-2 text-3xl sm:text-4xl font-semibold tracking-tight">Tool Catalog & Review Console</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Review claim provenance, audit pricing evidence, set Pathwise Picks, and monitor tool link freshness.
            </p>
          </div>
          <div className="flex items-center gap-2 self-start sm:self-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCheckAllLinks}
              disabled={checkingLinks}
              className="gap-2 text-xs"
            >
              <Activity className={checkingLinks ? "size-3.5 animate-spin" : "size-3.5 text-primary"} />
              {checkingLinks ? "Checking Links..." : "Run Link Check"}
            </Button>
            <Button variant="outline" size="sm" onClick={load} className="gap-2">
              <RefreshCw className={loading ? "size-4 animate-spin" : "size-4"} /> Refresh
            </Button>
          </div>
        </div>

        {error ? (
          <div role="alert" className="mt-6 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        {success ? (
          <div className="mt-6 rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-4 text-sm text-emerald-600 dark:text-emerald-400">
            {success}
          </div>
        ) : null}

        {/* VIEW NAVIGATION TABS */}
        <div className="mt-8 flex gap-3 border-b border-border pb-4">
          <Button
            variant={adminTab === "catalog" ? "default" : "outline"}
            size="sm"
            onClick={() => setAdminTab("catalog")}
            className="gap-2"
          >
            <BookOpen className="size-4" /> Tool Directory ({tools.length})
          </Button>
          <Button
            variant={adminTab === "import" ? "default" : "outline"}
            size="sm"
            onClick={() => setAdminTab("import")}
            className="gap-2"
          >
            <UploadCloud className="size-4" /> Import Cards (JSON)
          </Button>
          <Button
            variant={adminTab === "metrics" ? "default" : "outline"}
            size="sm"
            onClick={() => {
              setAdminTab("metrics");
              loadMetrics();
            }}
            className="gap-2"
          >
            <BarChart3 className="size-4" /> Tool Usage Metrics
          </Button>
        </div>

        {adminTab === "import" ? (
          <div className="mt-6 space-y-6">
            <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold flex items-center gap-2">
                    <UploadCloud className="size-5 text-primary" /> Import Tool Cards (Catalog v3)
                  </h2>
                  <p className="text-xs text-muted-foreground mt-1">
                    Upload or paste JSON matching Section 3 specification. Claims are strictly re-validated in code, evidence URLs are checked against official domains, and quotes are verified.
                  </p>
                </div>
                <div>
                  <label className="cursor-pointer inline-flex items-center gap-2 rounded-lg border border-border bg-secondary hover:bg-secondary/80 px-3.5 py-2 text-xs font-medium text-foreground transition-colors">
                    <UploadCloud className="size-4" /> Upload JSON File
                    <input
                      type="file"
                      accept=".json"
                      className="hidden"
                      onChange={handleFileUpload}
                    />
                  </label>
                </div>
              </div>

              <div className="mt-4">
                <Textarea
                  value={importJson}
                  onChange={(e) => setImportJson(e.target.value)}
                  placeholder={`[\n  {\n    "name": "Cursor",\n    "domain": "software",\n    "official_url": "https://cursor.com",\n    "pricing_url": "https://cursor.com/pricing",\n    "pricing_model": "freemium",\n    "has_free_tier": true,\n    "jobs": ["write_code", "debug_code"],\n    "tagline": "AI code editor...",\n    "summary": "...",\n    "how_it_helps": "...",\n    "pros": ["...", "...", "..."],\n    "cons": ["...", "...", "..."]\n  }\n]`}
                  rows={12}
                  className="font-mono text-xs"
                />
              </div>

              {importError ? (
                <div role="alert" className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive flex items-center gap-2">
                  <AlertCircle className="size-4 shrink-0" />
                  {importError}
                </div>
              ) : null}

              <div className="mt-4 flex items-center gap-3">
                <Button
                  onClick={handleImportCards}
                  disabled={importing || !importJson.trim()}
                  className="gap-2"
                >
                  {importing ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                  {importing ? "Importing & Verifying Claims..." : "Run Card Import"}
                </Button>
                {importJson ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setImportJson("");
                      setImportError("");
                      setImportResponse(null);
                    }}
                  >
                    Clear Input
                  </Button>
                ) : null}
              </div>
            </div>

            {/* IMPORT RESULTS DISPLAY */}
            {importResponse ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
                    <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Created</span>
                    <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">{importResponse.created}</p>
                  </div>
                  <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-4">
                    <span className="text-xs font-medium text-blue-600 dark:text-blue-400">Updated</span>
                    <p className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">{importResponse.updated}</p>
                  </div>
                  <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4">
                    <span className="text-xs font-medium text-rose-600 dark:text-rose-400">Rejected / Errors</span>
                    <p className="text-2xl font-bold text-rose-600 dark:text-rose-400 mt-1">{importResponse.rejected}</p>
                  </div>
                  <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
                    <span className="text-xs font-medium text-amber-600 dark:text-amber-400">Missing from Seed</span>
                    <p className="text-2xl font-bold text-amber-600 dark:text-amber-400 mt-1">{importResponse.missing_tools?.length || 0}</p>
                  </div>
                </div>

                {importResponse.missing_tools && importResponse.missing_tools.length > 0 ? (
                  <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
                    <h3 className="text-xs font-semibold text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                      <AlertTriangle className="size-4" /> Missing Expected Seed Tools ({importResponse.missing_tools.length})
                    </h3>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {importResponse.missing_tools.map((name) => (
                        <span key={name} className="rounded bg-amber-500/20 px-2 py-0.5 text-xs text-amber-800 dark:text-amber-200">
                          {name}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
                  <h3 className="text-sm font-semibold mb-3">Per-Card Import Results ({importResponse.results.length})</h3>
                  <div className="space-y-3">
                    {importResponse.results.map((res, i) => (
                      <div
                        key={i}
                        className="rounded-lg border border-border/80 bg-muted/20 p-3.5 flex flex-col gap-2"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm">{res.name}</span>
                            <span
                              className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                                res.status === "created"
                                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                                  : res.status === "updated"
                                  ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                                  : "bg-rose-500/10 text-rose-600 dark:text-rose-400"
                              }`}
                            >
                              {res.status}
                            </span>
                            {res.tool_id ? (
                              <span className="text-[11px] text-muted-foreground font-mono">
                                ID: #{res.tool_id}
                              </span>
                            ) : null}
                          </div>
                        </div>

                        {res.error ? (
                          <p className="text-xs text-rose-500 font-medium">{res.error}</p>
                        ) : null}

                        {res.flags && res.flags.length > 0 ? (
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {res.flags.map((flag, idx) => (
                              <span
                                key={idx}
                                className={`rounded px-2 py-0.5 text-[11px] font-mono ${
                                  flag.startsWith("quote mismatch") || flag.startsWith("evidence off-domain")
                                    ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20"
                                    : flag.startsWith("check:")
                                    ? "bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20"
                                    : "bg-secondary text-muted-foreground"
                                }`}
                              >
                                {flag}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-[11px] text-muted-foreground italic">No review flags.</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        ) : adminTab === "metrics" ? (
          <div className="mt-6 space-y-6">
            <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold flex items-center gap-2">
                    <BarChart3 className="size-5 text-primary" /> Creator Usage Signals & Per-Tool Metrics
                  </h2>
                  <p className="text-xs text-muted-foreground mt-1">
                    Monitors real-world creator outcomes from workflow steps. Public cards show "Used in N workflows" only once a tool has at least 10 feedback entries. Individual creator notes are strictly confidential and never displayed publicly.
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadMetrics}
                  disabled={loadingMetrics}
                  className="gap-2 text-xs self-start sm:self-auto"
                >
                  <RefreshCw className={loadingMetrics ? "size-3.5 animate-spin" : "size-3.5"} />
                  Refresh Metrics
                </Button>
              </div>

              {/* Metrics Summary Cards */}
              <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="rounded-xl border border-border bg-muted/20 p-4">
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Total Feedbacks
                  </p>
                  <p className="mt-1 text-2xl font-bold text-foreground">
                    {metrics.reduce((acc, m) => acc + m.total_feedbacks, 0)}
                  </p>
                </div>
                <div className="rounded-xl border border-border bg-muted/20 p-4">
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Tools With Signals
                  </p>
                  <p className="mt-1 text-2xl font-bold text-foreground">
                    {metrics.filter((m) => m.total_feedbacks > 0).length}
                  </p>
                </div>
                <div className="rounded-xl border border-border bg-muted/20 p-4">
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Public Badge (≥10)
                  </p>
                  <p className="mt-1 text-2xl font-bold text-primary">
                    {metrics.filter((m) => m.total_feedbacks >= 10).length}
                  </p>
                </div>
                <div className="rounded-xl border border-border bg-muted/20 p-4">
                  <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Avg Success Rate
                  </p>
                  <p className="mt-1 text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                    {(() => {
                      const withRates = metrics.filter((m) => m.success_rate_percent != null);
                      if (!withRates.length) return "N/A";
                      const avg =
                        withRates.reduce((acc, m) => acc + (m.success_rate_percent || 0), 0) /
                        withRates.length;
                      return `${avg.toFixed(1)}%`;
                    })()}
                  </p>
                </div>
              </div>

              {/* Metrics Table */}
              <div className="mt-6 overflow-x-auto rounded-xl border border-border">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/40 border-b border-border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    <tr>
                      <th className="py-3 px-4">Tool Name</th>
                      <th className="py-3 px-4">Domain</th>
                      <th className="py-3 px-4 text-center">Workflows</th>
                      <th className="py-3 px-4 text-center">Feedbacks</th>
                      <th className="py-3 px-4 text-center">Worked / Partly / Didn't</th>
                      <th className="py-3 px-4 text-center">Success Rate</th>
                      <th className="py-3 px-4 text-right">Public Badge Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {loadingMetrics ? (
                      <tr>
                        <td colSpan={7} className="py-12 text-center text-muted-foreground">
                          <Loader2 className="size-6 animate-spin mx-auto mb-2 text-primary" />
                          Loading usage metrics...
                        </td>
                      </tr>
                    ) : metrics.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-12 text-center text-muted-foreground">
                          No tool feedback recorded yet. Usage signals will populate as creators complete workflow steps.
                        </td>
                      </tr>
                    ) : (
                      metrics.map((m) => {
                        const hasRate = m.success_rate_percent != null;
                        const rate = m.success_rate_percent || 0;
                        const rateColor =
                          rate >= 80
                            ? "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                            : rate >= 50
                            ? "text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/20"
                            : "text-rose-600 dark:text-rose-400 bg-rose-500/10 border-rose-500/20";

                        return (
                          <tr key={m.tool_id} className="hover:bg-muted/20 transition-colors">
                            <td className="py-3.5 px-4 font-semibold text-foreground">
                              {m.name}
                            </td>
                            <td className="py-3.5 px-4 text-muted-foreground capitalize">
                              {m.domain?.replace("_", " ") || "—"}
                            </td>
                            <td className="py-3.5 px-4 text-center font-mono">
                              {m.used_in_workflows}
                            </td>
                            <td className="py-3.5 px-4 text-center font-mono font-semibold">
                              {m.total_feedbacks}
                            </td>
                            <td className="py-3.5 px-4 text-center">
                              <span className="font-mono text-emerald-600 dark:text-emerald-400 font-semibold">{m.worked_count}</span>
                              <span className="text-muted-foreground mx-1">/</span>
                              <span className="font-mono text-amber-600 dark:text-amber-400 font-semibold">{m.partly_count}</span>
                              <span className="text-muted-foreground mx-1">/</span>
                              <span className="font-mono text-rose-600 dark:text-rose-400 font-semibold">{m.didnt_count}</span>
                            </td>
                            <td className="py-3.5 px-4 text-center">
                              {hasRate ? (
                                <span className={`inline-flex px-2 py-0.5 rounded font-mono font-semibold border ${rateColor}`}>
                                  {rate.toFixed(1)}%
                                </span>
                              ) : (
                                <span className="text-muted-foreground italic">No signals</span>
                              )}
                            </td>
                            <td className="py-3.5 px-4 text-right">
                              {m.total_feedbacks >= 10 ? (
                                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary bg-primary/10 border border-primary/20 px-2 py-0.5 rounded">
                                  <CheckCircle2 className="size-3" /> Publicly Active ({m.total_feedbacks})
                                </span>
                              ) : (
                                <span className="text-[11px] text-muted-foreground">
                                  {m.total_feedbacks}/10 (Hidden)
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* CREATE TOOL CARD */}
            <div className="mt-6 rounded-xl border border-border bg-card p-6 shadow-sm">
              <h2 className="text-base font-semibold">Add New Tool</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Quickly add a candidate tool card. You can verify and attach claim evidence via the review console.
              </p>

              <form onSubmit={add} className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-[1.2fr_1.5fr_1.5fr_1.5fr_auto]">
                <Input name="name" placeholder="Tool name (e.g. Supabase)" required />
                <Input name="docs_url" placeholder="Docs URL" />
                <Input name="url" placeholder="Primary Tool URL" />
                <Input name="affiliate_url" placeholder="Affiliate URL (e.g. ?via=pathwise)" />
                <Button type="submit" disabled={adding} className="h-10 px-5">
                  {adding ? <Loader2 className="size-4 animate-spin mr-2" /> : <Sparkles className="size-4 mr-2" />}
                  Add tool
                </Button>
              </form>
            </div>

            {/* STATUS FILTER PILLS */}
            <div className="mt-8 flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap gap-2">
                {[
                  { label: "All Tools", value: "" },
                  { label: "Drafts", value: "draft" },
                  { label: "Verified", value: "verified" },
                  { label: "Hidden", value: "hidden" },
                  { label: "Stale (>30d)", value: "stale" },
                ].map((tab) => (
                  <Button
                    key={tab.value}
                    size="sm"
                    variant={statusFilter === tab.value ? "default" : "secondary"}
                    onClick={() => setStatusFilter(tab.value)}
                    className="rounded-lg text-xs"
                  >
                    {tab.label}
                  </Button>
                ))}
              </div>
              <span className="text-xs text-muted-foreground font-medium">
                {tools.length} tool{tools.length === 1 ? "" : "s"} listed
              </span>
            </div>

            {/* TOOLS TABLE */}
            <div className="mt-4 rounded-xl border border-border bg-card shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                {loading && tools.length === 0 ? (
                  <div className="flex items-center justify-center py-16 text-muted-foreground gap-3">
                    <Loader2 className="size-5 animate-spin text-primary" /> Loading catalog...
                  </div>
                ) : tools.length === 0 ? (
                  <div className="py-16 text-center text-sm text-muted-foreground">
                    No tools found for the selected filter.
                  </div>
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-border bg-muted/40 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      <tr>
                        <th className="py-3.5 px-4">Tool</th>
                        <th className="py-3.5 px-4">Domain & Jobs</th>
                        <th className="py-3.5 px-4">Pricing & Verification</th>
                        <th className="py-3.5 px-4">Links & Affiliate</th>
                        <th className="py-3.5 px-4">Status</th>
                        <th className="py-3.5 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {tools.map((t) => {
                        const isEditingAffiliate = editingAffiliateId === t.id;
                        const effectiveUrl = t.affiliate_url || t.url;
                        return (
                          <tr key={t.id} className="hover:bg-muted/30 transition-colors">
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2.5">
                                <div className="size-8 rounded-lg border border-border bg-muted/40 flex items-center justify-center overflow-hidden shrink-0">
                                  {t.logo_url ? (
                                    <img
                                      src={t.logo_url}
                                      alt={t.name}
                                      className="size-full object-contain p-0.5"
                                      onError={(e) => {
                                        (e.currentTarget as HTMLImageElement).style.display = "none";
                                      }}
                                    />
                                  ) : (
                                    <span className="text-[11px] font-bold text-muted-foreground font-mono">
                                      {t.name.slice(0, 2).toUpperCase()}
                                    </span>
                                  )}
                                </div>
                                <div>
                                  <div className="font-semibold text-foreground flex items-center gap-1.5">
                                    <span>{t.name}</span>
                                    {t.is_pick ? (
                                      <span
                                        className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-1.5 py-0.2 text-[10px] font-semibold text-amber-600 dark:text-amber-400"
                                        title="Pathwise Pick"
                                      >
                                        <Star className="size-2.5 fill-amber-500 text-amber-500" /> Pick
                                      </span>
                                    ) : null}
                                    {effectiveUrl ? (
                                      <a
                                        href={effectiveUrl}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-muted-foreground hover:text-primary inline-flex items-center"
                                        title="Open tool link"
                                      >
                                        <ExternalLink className="size-3" />
                                      </a>
                                    ) : null}
                                  </div>
                                  <div className="mt-1 flex items-center gap-2">
                                    {t.link_status === "ok" ? (
                                      <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                                        <CheckCircle2 className="size-3" /> Reachable
                                      </span>
                                    ) : t.link_status === "dead" ? (
                                      <span className="inline-flex items-center gap-1 text-[11px] text-rose-600 dark:text-rose-400 font-medium">
                                        <AlertTriangle className="size-3" /> Dead Link
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                                        <Globe className="size-3" /> Unchecked
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="py-3 px-4">
                              <span className="inline-block rounded-md bg-primary/10 text-primary px-2 py-0.5 text-xs font-semibold capitalize mb-1">
                                {t.domain || t.category || "general"}
                              </span>
                              <div className="flex flex-wrap gap-1 max-w-xs">
                                {(t.jobs || []).slice(0, 2).map((job, idx) => (
                                  <span key={idx} className="rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground font-mono">
                                    {job}
                                  </span>
                                ))}
                                {(t.jobs || []).length > 2 ? (
                                  <span className="text-[10px] text-muted-foreground self-center">
                                    +{(t.jobs || []).length - 2} more
                                  </span>
                                ) : null}
                              </div>
                            </td>
                            <td className="py-3 px-4">
                              <div className="space-y-1">
                                <div className="flex items-center gap-1.5">
                                  <span className="rounded bg-muted px-2 py-0.5 text-xs font-medium capitalize">
                                    {t.pricing_model || t.pricing || "freemium"}
                                  </span>
                                  {t.has_free_tier ? (
                                    <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-400">
                                      Free tier
                                    </span>
                                  ) : null}
                                </div>
                                {t.verified_at ? (
                                  <div className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                                    <ShieldCheck className="size-3" />
                                    <span>
                                      Verified {new Date(t.verified_at).toLocaleDateString("en-US", { month: "short", year: "numeric" })}
                                    </span>
                                  </div>
                                ) : (
                                  <span className="text-[11px] text-muted-foreground italic">Unverified</span>
                                )}
                              </div>
                            </td>
                            <td className="py-3 px-4">
                              {isEditingAffiliate ? (
                                <div className="flex items-center gap-1.5 min-w-[240px]">
                                  <Input
                                    value={affiliateInput}
                                    onChange={(e) => setAffiliateInput(e.target.value)}
                                    placeholder="https://affiliate.example.com"
                                    className="h-8 text-xs font-mono"
                                    autoFocus
                                  />
                                  <Button
                                    size="sm"
                                    className="h-8 px-2 text-xs"
                                    onClick={() => saveAffiliateUrl(t.id)}
                                  >
                                    <Check className="size-3.5" />
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-8 px-2 text-xs"
                                    onClick={() => {
                                      setEditingAffiliateId(null);
                                      setAffiliateInput("");
                                    }}
                                  >
                                    ✕
                                  </Button>
                                </div>
                              ) : (
                                <div className="flex flex-col gap-1 text-xs">
                                  {t.affiliate_url ? (
                                    <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-mono">
                                      <Link2 className="size-3 shrink-0" />
                                      <span className="truncate max-w-[180px]" title={t.affiliate_url}>
                                        {t.affiliate_url}
                                      </span>
                                      <button
                                        onClick={() => {
                                          setEditingAffiliateId(t.id);
                                          setAffiliateInput(t.affiliate_url || "");
                                        }}
                                        className="text-[11px] underline opacity-70 hover:opacity-100"
                                      >
                                        edit
                                      </button>
                                    </div>
                                  ) : (
                                    <button
                                      onClick={() => {
                                        setEditingAffiliateId(t.id);
                                        setAffiliateInput(t.url || "");
                                      }}
                                      className="text-muted-foreground hover:text-primary text-xs inline-flex items-center gap-1"
                                    >
                                      <Link2 className="size-3" /> + Add affiliate
                                    </button>
                                  )}
                                </div>
                              )}
                            </td>
                            <td className="py-3 px-4">
                              <select
                                className="rounded-md border border-border bg-background px-2.5 py-1 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-primary"
                                value={t.status}
                                onChange={(e) => {
                                  const nextStatus = e.target.value as any;
                                  if (nextStatus === "verified" && (t.review_flags?.length || 0) > 0) {
                                    openReviewDrawer(t);
                                    setError(
                                      `Cannot directly verify "${t.name}". Please review and resolve the ${t.review_flags?.length} review flag(s) in the drawer first.`
                                    );
                                    return;
                                  }
                                  run(
                                    () =>
                                      api.updateAdminTool(t.id, {
                                        status: nextStatus,
                                      }),
                                    `Status updated to ${nextStatus}`
                                  );
                                }}
                              >
                                <option value="draft">draft</option>
                                <option value="researched">researched</option>
                                <option value="verified">verified</option>
                                <option value="hidden">hidden</option>
                              </select>
                            </td>
                            <td className="py-3 px-4 text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 gap-1 text-xs px-2.5"
                                  onClick={() => openReviewDrawer(t)}
                                >
                                  <Edit3 className="size-3.5" /> Review card
                                </Button>
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="text-muted-foreground hover:text-destructive size-8"
                                  aria-label={`Delete ${t.name}`}
                                  onClick={() => {
                                    if (confirm(`Are you sure you want to delete "${t.name}"?`)) {
                                      run(() => api.deleteAdminTool(t.id), `Deleted "${t.name}"`);
                                    }
                                  }}
                                >
                                  <Trash2 className="size-4" />
                                </Button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </>
        )}

        {/* REVIEW & EDIT TOOL CARD DRAWER */}
        <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
          <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto p-6">
            <SheetHeader className="pb-4 border-b border-border">
              <div className="flex items-center justify-between">
                <SheetTitle className="flex items-center gap-2 text-xl font-bold">
                  <FileCode className="size-5 text-primary" />
                  Review: {selectedTool?.name}
                </SheetTitle>
                {selectedTool?.status === "verified" ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                    <CheckCircle2 className="size-3.5" /> Verified
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2.5 py-0.5 text-xs font-semibold text-amber-600 dark:text-amber-400">
                    <Clock className="size-3.5" /> Draft / Pending Review
                  </span>
                )}
              </div>
              <SheetDescription className="text-xs">
                Inspect claim provenance, edit critical taxonomy slugs, review quotes against official domains, and publish.
              </SheetDescription>
            </SheetHeader>

            <form onSubmit={handleDrawerSave} className="mt-6 space-y-6">
              {/* TOP DIAGNOSTICS & PATHWISE PICK TOGGLE */}
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-lg border border-border/80 bg-muted/20">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-foreground">Reachability:</span>
                    {selectedTool?.link_status === "ok" ? (
                      <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                        <CheckCircle2 className="size-3" /> OK (Reachable)
                      </span>
                    ) : selectedTool?.link_status === "dead" ? (
                      <span className="inline-flex items-center gap-1 rounded bg-rose-500/10 px-2 py-0.5 text-xs font-medium text-rose-600 dark:text-rose-400">
                        <AlertTriangle className="size-3" /> Dead / Hidden
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                        <Globe className="size-3" /> Unchecked
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-muted-foreground">
                    Domain: <strong className="text-primary font-mono">{formData.domain}</strong>
                  </span>
                </div>

                {/* PATHWISE PICK TOGGLE */}
                <div className="flex items-center justify-between rounded-lg border border-border bg-card p-3">
                  <div>
                    <div className="flex items-center gap-1.5 text-xs font-semibold">
                      <Star className={`size-3.5 ${formData.is_pick ? "fill-amber-400 text-amber-500" : "text-muted-foreground"}`} />
                      <span>Pathwise Pick</span>
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      Feature this tool at the top of recommendations. (Allowed only for verified tools.)
                    </p>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.is_pick}
                      disabled={formData.status !== "verified" && selectedTool?.status !== "verified"}
                      onChange={(e) => setFormData({ ...formData, is_pick: e.target.checked })}
                      className="size-4 rounded border-border text-primary focus:ring-primary disabled:opacity-50"
                    />
                    <span className="text-xs font-medium">
                      {formData.is_pick ? "Selected Pick" : "Standard"}
                    </span>
                  </label>
                </div>
              </div>

              {/* REVIEW FLAGS PROMINENT DISPLAY */}
              {formData.review_flags.length > 0 ? (
                <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-semibold text-amber-700 dark:text-amber-300">
                      <AlertTriangle className="size-4 shrink-0 text-amber-600 dark:text-amber-400" />
                      <span>Unresolved Review Flags ({formData.review_flags.length})</span>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => setFormData({ ...formData, review_flags: [] })}
                      className="h-7 text-[11px] gap-1 border-amber-500/40 text-amber-700 dark:text-amber-300 hover:bg-amber-500/20"
                    >
                      <CheckCheck className="size-3" /> Clear / Mark All Resolved
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {formData.review_flags.map((flag, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1.5 rounded-md border border-amber-500/30 bg-background/80 px-2.5 py-1 text-xs font-mono text-amber-800 dark:text-amber-200"
                      >
                        <span>{flag}</span>
                        <button
                          type="button"
                          onClick={() =>
                            setFormData({
                              ...formData,
                              review_flags: formData.review_flags.filter((_, i) => i !== idx),
                            })
                          }
                          className="text-muted-foreground hover:text-foreground text-xs"
                          title="Dismiss flag"
                        >
                          ✕
                        </button>
                      </span>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-300">
                  <CheckCircle2 className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  <span>All review flags resolved. Tool meets flag clearance criteria.</span>
                </div>
              )}

              {/* CRITICAL FIELDS & EVIDENCE COMPARISON */}
              <div className="rounded-xl border border-border bg-card p-4 space-y-4">
                <div className="flex items-center justify-between border-b border-border pb-2">
                  <h3 className="text-sm font-semibold flex items-center gap-1.5">
                    <ShieldCheck className="size-4 text-primary" /> Critical Fields & Claim Evidence
                  </h3>
                  <span className="text-[11px] text-muted-foreground">Checked against official pages</span>
                </div>

                {/* 1. Pricing Model */}
                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-foreground">Pricing Model</label>
                    <span className="text-[11px] font-mono text-muted-foreground">pricing_model</span>
                  </div>
                  <select
                    className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium focus:ring-1 focus:ring-primary"
                    value={formData.pricing_model}
                    onChange={(e) => setFormData({ ...formData, pricing_model: e.target.value })}
                  >
                    <option value="freemium">freemium</option>
                    <option value="free">free</option>
                    <option value="free_trial">free_trial</option>
                    <option value="paid">paid</option>
                    <option value="open_source">open_source</option>
                    <option value="unknown">unknown</option>
                  </select>
                  {renderEvidenceBlock("Pricing Model", selectedTool?.evidence?.pricing_model)}
                </div>

                {/* 2. Free Tier & Free Tier Summary */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-foreground">Has Free Tier?</label>
                    <select
                      className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium focus:ring-1 focus:ring-primary"
                      value={formData.has_free_tier === null ? "null" : String(formData.has_free_tier)}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          has_free_tier: e.target.value === "null" ? null : e.target.value === "true",
                        })
                      }
                    >
                      <option value="true">Yes (True)</option>
                      <option value="false">No (False)</option>
                      <option value="null">Unset / Null</option>
                    </select>
                    {renderEvidenceBlock("Has Free Tier", selectedTool?.evidence?.has_free_tier)}
                  </div>

                  <div>
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-foreground">Starting Price ($ / mo)</label>
                      <span className="text-[11px] font-mono text-muted-foreground">starting_price</span>
                    </div>
                    <Input
                      type="number"
                      step="any"
                      className="mt-1 text-xs"
                      value={formData.starting_price_monthly_usd}
                      onChange={(e) => setFormData({ ...formData, starting_price_monthly_usd: e.target.value })}
                      placeholder="e.g. 20"
                    />
                    {renderEvidenceBlock("Starting Price", selectedTool?.evidence?.starting_price_monthly_usd)}
                  </div>
                </div>

                {/* 3. Free Tier Summary & Limits */}
                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-foreground">Free Tier Summary</label>
                    <span className="text-[11px] font-mono text-muted-foreground">
                      {formData.free_tier_summary.length} / 140 chars
                    </span>
                  </div>
                  <Input
                    className="mt-1 text-xs"
                    value={formData.free_tier_summary}
                    onChange={(e) => setFormData({ ...formData, free_tier_summary: e.target.value })}
                    placeholder="Concise one-line summary of what is free..."
                    maxLength={140}
                  />
                  {renderEvidenceBlock("Free Tier Summary", selectedTool?.evidence?.free_tier_summary)}
                </div>

                {/* 4. Credit Card & Commercial Use */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-foreground">Credit Card Required for Free Tier?</label>
                    <select
                      className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium focus:ring-1 focus:ring-primary"
                      value={formData.credit_card_required === null ? "null" : String(formData.credit_card_required)}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          credit_card_required: e.target.value === "null" ? null : e.target.value === "true",
                        })
                      }
                    >
                      <option value="null">Unset / Null</option>
                      <option value="false">No (No Card Required)</option>
                      <option value="true">Yes (Card Required)</option>
                    </select>
                    {renderEvidenceBlock("Credit Card", selectedTool?.evidence?.credit_card_required)}
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-foreground">Commercial Use on Free Tier?</label>
                    <select
                      className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium focus:ring-1 focus:ring-primary"
                      value={formData.commercial_use_on_free === null ? "null" : String(formData.commercial_use_on_free)}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          commercial_use_on_free: e.target.value === "null" ? null : e.target.value === "true",
                        })
                      }
                    >
                      <option value="null">Unset / Null</option>
                      <option value="true">Yes (Commercial Allowed)</option>
                      <option value="false">No (Personal / Non-commercial Only)</option>
                    </select>
                    {renderEvidenceBlock("Commercial Use", selectedTool?.evidence?.commercial_use_on_free)}
                  </div>
                </div>

                {/* 5. Watermark & Skill Level */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-foreground">Watermark on Free Plan?</label>
                    <select
                      className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium focus:ring-1 focus:ring-primary"
                      value={formData.watermark_on_free === null ? "null" : String(formData.watermark_on_free)}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          watermark_on_free: e.target.value === "null" ? null : e.target.value === "true",
                        })
                      }
                    >
                      <option value="null">Unset / Null</option>
                      <option value="false">No Watermark</option>
                      <option value="true">Watermark Included</option>
                    </select>
                    {renderEvidenceBlock("Watermark", selectedTool?.evidence?.watermark_on_free)}
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-foreground">Skill Level</label>
                    <select
                      className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium focus:ring-1 focus:ring-primary"
                      value={formData.skill_level}
                      onChange={(e) => setFormData({ ...formData, skill_level: e.target.value })}
                    >
                      <option value="all">all (everyone)</option>
                      <option value="beginner">beginner</option>
                      <option value="intermediate">intermediate</option>
                      <option value="advanced">advanced</option>
                    </select>
                    {renderEvidenceBlock("Skill Level", selectedTool?.evidence?.skill_level)}
                  </div>
                </div>

                {/* 6. Platforms */}
                <div>
                  <label className="text-xs font-semibold text-foreground">Platforms (comma-separated)</label>
                  <Input
                    className="mt-1 text-xs"
                    value={formData.platformsText}
                    onChange={(e) => setFormData({ ...formData, platformsText: e.target.value })}
                    placeholder="web, mac, windows, linux, ios, android, cli"
                  />
                  {renderEvidenceBlock("Platforms", selectedTool?.evidence?.platforms)}
                </div>
              </div>

              {/* TOOL LOGO & PREVIEW PIPELINE (Slice C8) */}
              <div className="rounded-xl border border-border bg-card p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-border/80 pb-2">
                  <span className="text-xs font-semibold flex items-center gap-1.5">
                    <Sparkles className="size-3.5 text-primary" /> Tool Logo & Preview Pipeline
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-md border border-border bg-muted/40 text-muted-foreground capitalize">
                    Source: {formData.logo_source || selectedTool?.logo_source || "none"}
                  </span>
                </div>

                <div className="flex items-center gap-4">
                  <div className="size-14 rounded-xl border border-border bg-muted/40 flex items-center justify-center overflow-hidden shrink-0 shadow-xs">
                    {formData.logo_url ? (
                      <img
                        src={formData.logo_url}
                        alt={formData.name}
                        loading="lazy"
                        className="size-full object-contain p-1"
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).style.display = "none";
                        }}
                      />
                    ) : (
                      <span className="text-base font-bold text-muted-foreground font-mono">
                        {formData.name.slice(0, 2).toUpperCase()}
                      </span>
                    )}
                  </div>

                  <div className="flex-1 space-y-1.5">
                    <p className="text-xs font-mono text-muted-foreground truncate" title={formData.logo_url}>
                      {formData.logo_url || "No logo stored"}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 pt-0.5">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={handleFetchLogo}
                        disabled={logoActionLoading}
                        className="h-7 text-xs gap-1"
                      >
                        {logoActionLoading ? <Loader2 className="size-3 animate-spin" /> : <RefreshCw className="size-3" />}
                        Fetch logo
                      </Button>

                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setShowPasteUrl(!showPasteUrl)}
                        disabled={logoActionLoading}
                        className="h-7 text-xs gap-1"
                      >
                        <Link2 className="size-3" />
                        Paste logo URL
                      </Button>

                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".png,.jpg,.jpeg,.webp,.svg,.ico"
                        className="hidden"
                        onChange={handleUploadLogo}
                      />
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={logoActionLoading}
                        className="h-7 text-xs gap-1"
                      >
                        <UploadCloud className="size-3" />
                        Upload
                      </Button>
                    </div>
                  </div>
                </div>

                {showPasteUrl && (
                  <div className="pt-2 border-t border-border/60 flex items-center gap-2">
                    <Input
                      value={pasteUrlInput}
                      onChange={(e) => setPasteUrlInput(e.target.value)}
                      placeholder="https://example.com/logo.png"
                      className="text-xs font-mono h-8 flex-1"
                    />
                    <Button
                      type="button"
                      size="sm"
                      onClick={handlePasteLogoUrl}
                      disabled={logoActionLoading || !pasteUrlInput.trim()}
                      className="h-8 text-xs shrink-0"
                    >
                      {logoActionLoading ? <Loader2 className="size-3 animate-spin" /> : "Save URL"}
                    </Button>
                  </div>
                )}

                {logoMessage && (
                  <div
                    className={cn(
                      "text-[11px] p-2 rounded-lg font-medium",
                      logoMessage.error
                        ? "bg-destructive/10 text-destructive"
                        : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                    )}
                  >
                    {logoMessage.text}
                  </div>
                )}
              </div>

              {/* TAXONOMY DOMAIN & JOBS EDITING */}
              <div className="rounded-xl border border-border bg-card p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-border pb-2">
                  <h3 className="text-sm font-semibold flex items-center gap-1.5">
                    <Layers className="size-4 text-primary" /> Taxonomy Domain & Jobs
                  </h3>
                  <span className="text-[11px] text-muted-foreground">Nine official domains</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-foreground">Taxonomy Domain</label>
                    <select
                      className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium focus:ring-1 focus:ring-primary capitalize"
                      value={formData.domain}
                      onChange={(e) => setFormData({ ...formData, domain: e.target.value, category: e.target.value })}
                    >
                      {TAXONOMY_DOMAINS.map((dom) => (
                        <option key={dom} value={dom}>
                          {dom}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-foreground">Official Domains (comma-separated)</label>
                    <Input
                      className="mt-1 text-xs font-mono"
                      value={formData.official_domains}
                      onChange={(e) => setFormData({ ...formData, official_domains: e.target.value })}
                      placeholder="example.com, docs.example.com"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-foreground">Taxonomy Job Slugs (comma-separated)</label>
                  <Input
                    className="mt-1 text-xs font-mono"
                    value={formData.jobsText}
                    onChange={(e) => setFormData({ ...formData, jobsText: e.target.value })}
                    placeholder="write_code, debug_code, explain_code"
                  />
                </div>
              </div>

              {/* DESCRIPTIONS & LIMITS (TAGLINE, PROS, CONS) */}
              <div className="rounded-xl border border-border bg-card p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-border pb-2">
                  <h3 className="text-sm font-semibold">Explanations & Value Proposition</h3>
                  <span className="text-[11px] text-muted-foreground">Strict character & list limits</span>
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-foreground">Tagline</label>
                    <span className="text-[11px] font-mono text-muted-foreground">
                      {formData.tagline.length} / 90 chars
                    </span>
                  </div>
                  <Input
                    className="mt-1 text-xs"
                    value={formData.tagline}
                    onChange={(e) => setFormData({ ...formData, tagline: e.target.value })}
                    placeholder="Snappy one-liner for search and cards..."
                    maxLength={90}
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-foreground">Summary</label>
                  <Textarea
                    rows={2}
                    className="mt-1 text-xs"
                    value={formData.summary}
                    onChange={(e) => setFormData({ ...formData, summary: e.target.value })}
                    placeholder="Overview of tool capability..."
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-foreground">How It Helps</label>
                  <Textarea
                    rows={2}
                    className="mt-1 text-xs"
                    value={formData.how_it_helps}
                    onChange={(e) => setFormData({ ...formData, how_it_helps: e.target.value })}
                    placeholder="Specific workflow acceleration for the creator..."
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-foreground">Pros (exactly 3, one per line)</label>
                      <span className="text-[11px] font-mono text-muted-foreground">
                        {formData.prosText.split("\n").filter((p) => p.trim()).length} / 3
                      </span>
                    </div>
                    <Textarea
                      rows={3}
                      className="mt-1 text-xs"
                      value={formData.prosText}
                      onChange={(e) => setFormData({ ...formData, prosText: e.target.value })}
                      placeholder="Pro 1&#10;Pro 2&#10;Pro 3"
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-foreground">Cons (exactly 3, one per line)</label>
                      <span className="text-[11px] font-mono text-muted-foreground">
                        {formData.consText.split("\n").filter((c) => c.trim()).length} / 3
                      </span>
                    </div>
                    <Textarea
                      rows={3}
                      className="mt-1 text-xs"
                      value={formData.consText}
                      onChange={(e) => setFormData({ ...formData, consText: e.target.value })}
                      placeholder="Con 1&#10;Con 2&#10;Con 3"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-foreground">Best For</label>
                    <Textarea
                      rows={2}
                      className="mt-1 text-xs"
                      value={formData.best_for}
                      onChange={(e) => setFormData({ ...formData, best_for: e.target.value })}
                      placeholder="When is this tool optimal?"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-foreground">Not For / Limitations</label>
                    <Textarea
                      rows={2}
                      className="mt-1 text-xs"
                      value={formData.not_for}
                      onChange={(e) => setFormData({ ...formData, not_for: e.target.value })}
                      placeholder="When should an alternative be used?"
                    />
                  </div>
                </div>
              </div>

              {/* URLS & MONETIZATION */}
              <div className="rounded-xl border border-border bg-card p-4 space-y-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  URLs & Monetization
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-foreground">Official URL</label>
                    <Input
                      className="mt-1 text-xs font-mono"
                      value={formData.url}
                      onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                      required
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-foreground">Pricing URL</label>
                    <Input
                      className="mt-1 text-xs font-mono"
                      value={formData.pricing_url}
                      onChange={(e) => setFormData({ ...formData, pricing_url: e.target.value })}
                      placeholder="https://tool.com/pricing"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-medium text-foreground">Affiliate URL (Preserved during rechecks)</label>
                  <Input
                    className="mt-1 text-xs font-mono text-emerald-600 dark:text-emerald-400"
                    value={formData.affiliate_url}
                    onChange={(e) => setFormData({ ...formData, affiliate_url: e.target.value })}
                    placeholder="https://tool.com?via=pathwise"
                  />
                </div>
              </div>

              {/* FRESH CARD JSON RECHECK & DIFF INSPECTOR */}
              <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-semibold text-primary flex items-center gap-1.5">
                      <Sparkles className="size-4" /> Fresh JSON Recheck & Diff Inspector
                    </h3>
                    <p className="text-[11px] text-muted-foreground mt-0.5">
                      Paste fresh card JSON to calculate a field-by-field diff before applying.
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={handleCalculateDiff}
                    disabled={freshLoading || !freshCardJson.trim()}
                    className="h-7 text-xs gap-1"
                  >
                    {freshLoading ? <Loader2 className="size-3 animate-spin" /> : <Activity className="size-3" />}
                    Compare Diff
                  </Button>
                </div>

                <Textarea
                  value={freshCardJson}
                  onChange={(e) => setFreshCardJson(e.target.value)}
                  placeholder="Paste fresh card JSON here..."
                  rows={4}
                  className="font-mono text-xs"
                />

                {freshError ? (
                  <div className="rounded border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive flex items-center gap-1.5">
                    <AlertCircle className="size-3.5 shrink-0" /> {freshError}
                  </div>
                ) : null}

                {freshDiff ? (
                  <div className="rounded-lg border border-border bg-card p-3 space-y-2.5">
                    <div className="flex items-center justify-between border-b border-border pb-2">
                      <span className="text-xs font-semibold">
                        Field-by-Field Diff ({Object.keys(freshDiff).length} changed)
                      </span>
                      <Button
                        size="sm"
                        type="button"
                        onClick={handleApplyFreshCard}
                        disabled={freshLoading}
                        className="h-7 text-xs bg-emerald-600 hover:bg-emerald-700 text-white gap-1"
                      >
                        <Check className="size-3" /> Apply All Changes
                      </Button>
                    </div>
                    {Object.keys(freshDiff).length === 0 ? (
                      <p className="text-xs text-muted-foreground italic">No differences detected. Card is up to date.</p>
                    ) : (
                      <div className="space-y-1.5 max-h-60 overflow-y-auto">
                        {Object.entries(freshDiff).map(([field, vals]: [string, any]) => (
                          <div key={field} className="rounded border border-amber-500/30 bg-amber-500/5 p-2 text-[11px]">
                            <div className="font-semibold text-foreground">{field}</div>
                            <div className="grid grid-cols-2 gap-2 mt-1 font-mono text-[10px]">
                              <div>
                                <span className="text-muted-foreground block uppercase">Current:</span>
                                <span className="text-muted-foreground truncate block">
                                  {JSON.stringify(vals.current) ?? "—"}
                                </span>
                              </div>
                              <div>
                                <span className="text-primary block uppercase">New:</span>
                                <span className="text-primary font-semibold truncate block">
                                  {JSON.stringify(vals.new) ?? "—"}
                                </span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : null}
              </div>

              {/* SERVER VERIFICATION READINESS CHECKLIST */}
              <div className="rounded-xl border border-border bg-card p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-border pb-2">
                  <span className="text-xs font-semibold text-foreground">Catalog v3 Verification Checklist</span>
                  {allRulesPassed ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="size-3.5" /> All 8 rules satisfied
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                      <AlertTriangle className="size-3.5" /> {failedRules.length} requirement{failedRules.length === 1 ? "" : "s"} missing
                    </span>
                  )}
                </div>

                <ul className="space-y-1.5 text-xs">
                  {validationChecks.map((rule) => (
                    <li key={rule.id} className="flex items-center gap-2">
                      {rule.passed ? (
                        <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                      ) : (
                        <XCircle className="size-3.5 text-rose-500 shrink-0" />
                      )}
                      <span className={rule.passed ? "text-foreground" : "text-muted-foreground font-medium"}>
                        {rule.label}
                      </span>
                    </li>
                  ))}
                </ul>

                {!allRulesPassed ? (
                  <p className="text-[11px] text-amber-600/90 dark:text-amber-400/90 pt-1 border-t border-border/50">
                    "Verify & Publish" is disabled until all requirements above are satisfied.
                  </p>
                ) : null}
              </div>

              <SheetFooter className="pt-4 border-t border-border flex flex-col sm:flex-row gap-2">
                {formData.status !== "verified" ? (
                  <Button
                    type="button"
                    variant="default"
                    className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5"
                    disabled={savingDrawer || !allRulesPassed}
                    onClick={() => handleDrawerSave(undefined, "verified")}
                    title={!allRulesPassed ? "All verification rules must pass before publishing" : "Publish to live catalog"}
                  >
                    <CheckCircle2 className="size-4" /> Verify & Publish
                  </Button>
                ) : null}
                <Button type="submit" disabled={savingDrawer} className="gap-1.5">
                  {savingDrawer ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
                  Save Changes
                </Button>
              </SheetFooter>
            </form>
          </SheetContent>
        </Sheet>
      </main>
    </div>
  );
}
