"use client";

import { Check, Download, FileJson } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { ModelPowerBadge } from "@/components/model-power-badge";
import { Button } from "@/components/ui/button";
import { downloadApiFile } from "@/lib/api";
import type { GenerationRun, ImageModelInfo } from "@/lib/types";

export function GenerationDownloadActions({ run }: { run: GenerationRun }) {
  const selected = run.candidates.find(candidate => candidate.id === run.selected_candidate_id);
  const model: ImageModelInfo | undefined = selected ? {
    id: selected.model,
    display_name: selected.model_display_name,
    power_label: selected.model_power_label,
    power_level: selected.model_power_level,
    description: selected.model_description,
    recommended_for: [],
    cost_tier: selected.model_cost_tier,
  } : run.selected_model_info ?? undefined;
  const candidates = run.candidates.filter(candidate => candidate.image_path).length;
  const checks = run.candidates.reduce((total, candidate) => total + candidate.qa_findings.length, 0);
  const repairs = run.candidates.filter(candidate => candidate.repair_parent_id).length;
  const base = `/api/generation-engine/runs/${run.id}/download`;
  const fiveComic = ["five_story", "five-comic"].includes(run.story_format);

  return <section aria-label="Approved comic downloads" className="rounded-[28px] border border-emerald-200 bg-emerald-50 p-6 sm:p-7">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[.2em] text-emerald-800"><Check className="size-4" />Approved</p><h2 className="mt-2 text-2xl font-semibold">Comic ready for production</h2></div>{model && <ModelPowerBadge model={model} />}</div>
    <div className="mt-5 grid gap-3 rounded-2xl bg-white/70 p-4 text-xs sm:grid-cols-3 lg:grid-cols-6"><Metric label="Candidates" value={String(candidates)} /><Metric label="Automatic checks" value={String(checks)} /><Metric label="Repairs" value={String(repairs)} /><Metric label="Human decisions" value="1" /><Metric label="Runtime" value={formatRuntime(run.runtime_ms)} /><Metric label="Final QA" value={selected?.qa_status ?? "Unavailable"} /></div>
    <div className="mt-5 flex flex-wrap gap-2"><DownloadAction path={`${base}/final?format=png`} label="Download approved comic as PNG"><Download className="size-4" />Download PNG</DownloadAction><DownloadAction path={`${base}/final?format=jpg`} label="Download approved comic as JPG" variant="outline"><Download className="size-4" />Download JPG</DownloadAction><Button asChild variant="outline"><Link href={`/history?run=${encodeURIComponent(run.id)}`} aria-label="View this generation run in History">View History</Link></Button></div>
    {fiveComic && <div className="mt-4 flex flex-wrap gap-2">{Array.from({ length: run.comic_asset_count ?? 0 }, (_, index) => <DownloadAction key={index} path={`${base}/final?format=png&comic=${index + 1}`} label={`Download Comic ${index + 1}`} size="sm" variant="ghost">Comic {index + 1}</DownloadAction>)}<DownloadAction path={`${base}/all`} label="Download all five-comic story assets as ZIP" size="sm" variant="outline"><Download className="size-4" />Download All as ZIP</DownloadAction></div>}
    <details className="mt-4 text-xs"><summary className="cursor-pointer font-semibold text-emerald-900">More download options</summary><div className="mt-3 flex flex-wrap gap-2"><DownloadAction path={`${base}/candidates`} label="Download all generated candidates as ZIP" size="sm" variant="ghost"><Download className="size-4" />All candidates</DownloadAction><DownloadAction path={`${base}/qa`} label="Download the QA report as JSON" size="sm" variant="ghost"><FileJson className="size-4" />QA report</DownloadAction><DownloadAction path={`${base}/summary`} label="Download the generation summary as JSON" size="sm" variant="ghost"><FileJson className="size-4" />Run summary</DownloadAction></div></details>
  </section>;
}

function DownloadAction({ path, label, children, variant, size }: { path: string; label: string; children: React.ReactNode; variant?: "outline" | "ghost"; size?: "sm" }) {
  async function download() { try { await downloadApiFile(path); } catch (error) { toast.error(error instanceof Error ? error.message : "Download failed"); } }
  return <Button type="button" variant={variant} size={size} aria-label={label} onClick={() => void download()}>{children}</Button>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div><p className="text-[9px] font-bold uppercase tracking-[.12em] text-muted">{label}</p><p className="mt-1 font-semibold text-ink">{value}</p></div>; }
function formatRuntime(runtime: number | null) { if (runtime == null) return "Unavailable"; const seconds = Math.round(runtime / 1000); const minutes = Math.floor(seconds / 60); return minutes ? `${minutes}m ${seconds % 60}s` : `${seconds}s`; }
