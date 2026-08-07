import { API_URL } from "@/lib/api";
import type { GenerationCandidate, GenerationRun } from "@/lib/types";

export type ComicDisplayStatus = "Approved" | "Waiting for Approval" | "Passed" | "Draft" | "Cancelled" | "Failed";

export function comicStatus(run: GenerationRun): ComicDisplayStatus {
  if (run.status === "approved") return "Approved";
  if (run.status === "awaiting_human") return "Waiting for Approval";
  if (run.status === "rejected") return "Passed";
  if (run.status === "cancelled") return "Cancelled";
  if (run.status === "failed") return "Failed";
  return "Draft";
}

export function preferredCandidate(run: GenerationRun): GenerationCandidate | undefined {
  return run.candidates.find(candidate => candidate.id === run.selected_candidate_id)
    ?? run.candidates.find(candidate => candidate.recommended)
    ?? run.candidates.find(candidate => candidate.final_asset_url || candidate.asset_url);
}

export function assetUrl(path?: string | null): string {
  if (!path) return "";
  return /^https?:\/\//.test(path) ? path : `${API_URL}${path.startsWith("/") ? "" : "/"}${path}`;
}

export function comicThumbnail(run: GenerationRun): string {
  const candidate = preferredCandidate(run);
  return assetUrl(run.final_asset_url || candidate?.final_asset_url || candidate?.asset_url);
}

export function comicModel(run: GenerationRun): string {
  const candidate = preferredCandidate(run);
  return candidate ? `${candidate.model_power_label} · ${candidate.model_display_name}` : run.selected_model_info ? `${run.selected_model_info.power_label} · ${run.selected_model_info.display_name}` : run.model_selection_mode;
}

export function filterComics(runs: GenerationRun[], query: string, status: "All" | ComicDisplayStatus): GenerationRun[] {
  const clean = query.trim().toLowerCase();
  return runs.filter(run => {
    if (status !== "All" && comicStatus(run) !== status) return false;
    if (!clean) return true;
    return [run.concept_text, run.story_format, run.story_brief?.emotional_insight, run.source_channel]
      .some(value => String(value ?? "").toLowerCase().includes(clean));
  });
}
