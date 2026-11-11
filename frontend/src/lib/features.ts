// Build-time feature flags (F0). Both default OFF: when unset or anything
// other than "true"/"1", the feature stays hidden. Mirrors the backend
// FEATURE_LIVE_RUN / FEATURE_META_SHOWCASE settings.

function readFlag(name: string): boolean {
  const raw = (import.meta as any).env?.[name];
  if (typeof raw !== "string") return false;
  const value = raw.trim().toLowerCase();
  return value === "true" || value === "1";
}

export const FEATURE_LIVE_RUN = readFlag("VITE_FEATURE_LIVE_RUN");
export const FEATURE_META_SHOWCASE = readFlag("VITE_FEATURE_META_SHOWCASE");
