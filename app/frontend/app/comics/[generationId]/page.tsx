"use client";

import Image from "next/image";
import Link from "next/link";
import { AlertCircle, ArrowLeft, ArrowUpRight, Check, Download, RefreshCw, RotateCcw, Wrench, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { api, downloadApiFile } from "@/lib/api";
import { assetUrl, comicModel, comicStatus, preferredCandidate } from "@/lib/comics";
import type { AgentTask, GenerationCandidate, GenerationEvent, GenerationRun } from "@/lib/types";

export default function ComicDetailPage() {
  const { generationId } = useParams<{ generationId: string }>();
  const router = useRouter();
  const [run, setRun] = useState<GenerationRun>();
  const [loadError, setLoadError] = useState<string>();
  const [events, setEvents] = useState<GenerationEvent[]>([]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(async () => {
    const [record, timeline] = await Promise.all([
      api<GenerationRun>(`/api/generation-engine/runs/${generationId}`),
      api<GenerationEvent[]>(`/api/generation-engine/runs/${generationId}/events`).catch(() => []),
    ]);
    setRun(record); setEvents(timeline); setLoadError(undefined);
  }, [generationId]);
  useEffect(() => {
    let disposed = false;
    let poll: number | undefined;
    const refresh = async () => {
      try { await load(); }
      catch (error) { setLoadError(error instanceof Error ? error.message : "Comic details are unavailable."); }
      finally { if (!disposed) poll = window.setTimeout(() => void refresh(), 2500); }
    };
    void refresh();
    return () => { disposed = true; if (poll) window.clearTimeout(poll); };
  }, [load]);

  const candidate = useMemo(() => run ? preferredCandidate(run) : undefined, [run]);
  const finalImage = assetUrl(run?.final_asset_url || candidate?.final_asset_url || candidate?.asset_url);
  const originalCandidate = candidate?.repair_parent_id ? run?.candidates.find(item => item.id === candidate.repair_parent_id) ?? candidate : candidate;
  const originalImage = assetUrl(originalCandidate?.asset_url);

  async function decide(action: "approve" | "pass" | "fix") {
    if (!run) return; setBusy(action);
    try {
      const response = await api<{ task: AgentTask }>("/api/dinkly-agent/approvals", { method: "POST", body: JSON.stringify({ action, item_type: "comic", item_id: run.id, notes: notes.trim() || null, source_channel: "web", source_thread_id: `comic-${run.id}` }) });
      toast.success(action === "approve" ? "Comic approved" : action === "pass" ? "Comic passed" : "Repair task queued");
      if (action === "fix") router.push(`/agent/tasks/${response.task.id}`); else await load();
    } catch (error) { toast.error(error instanceof Error ? error.message : "Decision could not be saved"); }
    finally { setBusy(""); }
  }

  async function generateAnother() {
    if (!run) return; setBusy("another");
    try {
      const response = await api<{ task: AgentTask }>("/api/dinkly-agent/instructions", { method: "POST", body: JSON.stringify({ message: `Generate another version of ${run.concept_text}.`, thread_id: `comic-${run.id}`, user_id: "owner", context: { story_brief: run.story_brief } }) });
      router.push(`/agent/tasks/${response.task.id}`);
    } catch (error) { toast.error(error instanceof Error ? error.message : "New generation could not be queued"); }
    finally { setBusy(""); }
  }

  async function download(path: string) { try { const name = await downloadApiFile(path); toast.success(`${name} downloaded`); } catch (error) { toast.error(error instanceof Error ? error.message : "Download failed"); } }

  if (!run && loadError) return <div className="mx-auto max-w-4xl py-20 text-center"><AlertCircle className="mx-auto size-7 text-[#a14b3f]"/><h1 className="mt-4 text-2xl font-semibold">Comic details unavailable</h1><p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted">{loadError}</p><div className="mt-5 flex justify-center gap-2"><Button asChild variant="outline"><Link href="/comics"><ArrowLeft className="size-4"/>All comics</Link></Button><Button onClick={() => void load().catch((error: unknown) => setLoadError(error instanceof Error ? error.message : "Comic details are unavailable."))}><RefreshCw className="size-4"/>Retry</Button></div></div>;
  if (!run) return <div className="mx-auto max-w-6xl py-20 text-center text-sm text-muted">Opening comic details…</div>;
  const repairs = run.candidates.filter(item => item.repair_parent_id || item.repair_number);
  return <div className="mx-auto max-w-7xl space-y-7 pb-16">
    <div className="flex flex-wrap items-center justify-between gap-4"><Button asChild variant="ghost"><Link href="/comics"><ArrowLeft className="size-4"/>All comics</Link></Button><div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => void download(`/api/generation-engine/runs/${run.id}/download/original?candidate_id=${encodeURIComponent(originalCandidate?.id ?? "")}`)} disabled={!originalCandidate}><Download className="size-4"/>Download Original</Button><Button onClick={() => void download(`/api/generation-engine/runs/${run.id}/download/final?format=png`)} disabled={!finalImage}><Download className="size-4"/>Download Final</Button></div></div>
    <header className="flex flex-col justify-between gap-5 md:flex-row md:items-end"><div><div className="flex flex-wrap gap-2"><Badge>{comicStatus(run)}</Badge><Badge>{run.story_format.replaceAll("_", " ")}</Badge></div><h1 className="mt-3 text-3xl font-semibold tracking-[-.04em] sm:text-4xl">{run.concept_text}</h1><p className="mt-2 text-xs capitalize text-muted">{new Date(run.started_at).toLocaleString()} · {comicModel(run)} · from {run.source_channel ?? "web"}</p></div>{run.source_task_id && <Button asChild variant="outline"><Link href={`/agent/tasks/${run.source_task_id}`}>View source task <ArrowUpRight className="size-3.5"/></Link></Button>}</header>
    <section className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(300px,.8fr)]">
      <div><h2 className="mb-4 text-xl font-semibold">Final Image</h2><Card className="overflow-hidden"><div className="relative aspect-square bg-[#f6f0e3]">{finalImage ? <Image src={finalImage} alt={`Final ${run.concept_text}`} fill unoptimized className="object-contain p-3"/> : <div className="flex size-full items-center justify-center text-sm text-muted">Final image unavailable</div>}</div></Card></div>
      <div className="space-y-4"><Card><CardContent className="space-y-4 p-5"><h2 className="text-lg font-semibold">Human decision</h2><p className="text-xs leading-5 text-muted">Approve the recommended final, pass it, or describe the exact repair needed.</p><Textarea aria-label="Repair notes" value={notes} onChange={event => setNotes(event.target.value)} placeholder="Optional repair or decision notes"/><div className="flex flex-wrap gap-2"><Button onClick={() => void decide("approve")} disabled={Boolean(busy) || run.status === "approved"}><Check className="size-4"/>Approve</Button><Button variant="outline" onClick={() => void decide("fix")} disabled={Boolean(busy)}><Wrench className="size-4"/>Fix Issues</Button><Button variant="ghost" onClick={() => void decide("pass")} disabled={Boolean(busy) || run.status === "rejected"}><X className="size-4"/>Pass</Button></div><div className="grid gap-2 sm:grid-cols-2"><Button variant="outline" onClick={() => void generateAnother()} disabled={Boolean(busy)}><RotateCcw className="size-4"/>Generate Another</Button><Button asChild variant="outline"><a href="#story-brief">Open Story Brief</a></Button></div></CardContent></Card><div id="story-brief"><FactCard title="Story Brief"><StoryBrief run={run}/></FactCard></div><FactCard title="Prompt Recipe Summary"><ul className="space-y-2 text-xs leading-5">{(run.generation_recipe?.length ? run.generation_recipe : [run.prompt_record.template, `Character rules ${run.prompt_record.character_rule_version}`, `Failure rules ${run.prompt_record.failure_rule_version}`]).map(item => <li key={item}>• {item}</li>)}</ul></FactCard></div>
    </section>
    <DetailSection title="Candidates"><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{run.candidates.map(item => <CandidateCard key={item.id} candidate={item} selected={item.id === run.selected_candidate_id} finalApproved={run.status === "approved" && item.id === run.selected_candidate_id}/>)}</div></DetailSection>
    <section className="grid gap-6 lg:grid-cols-2"><FactCard title="QA"><p className="text-sm leading-6">{candidate?.qa_summary || "No QA summary recorded."}</p><ul className="mt-4 space-y-2">{candidate?.qa_findings.map(finding => <li key={`${finding.category}-${finding.check}`} className="rounded-xl bg-wash p-3 text-xs"><strong>{finding.status} · {finding.check}</strong><p className="mt-1 text-muted">{finding.detail}</p></li>)}</ul></FactCard><FactCard title="Repairs">{repairs.length ? <ol className="space-y-3">{repairs.map((repair, index) => <li key={repair.id} className="rounded-xl border border-line p-3 text-xs"><strong>Repair {repair.repair_number ?? index + 1} · Candidate {repair.label}</strong><p className="mt-1 text-muted">From {repair.repair_parent_id ?? "original"} · {repair.qa_status}</p></li>)}</ol> : <p className="text-sm text-muted">No repairs recorded.</p>}</FactCard></section>
    <DetailSection title="Original Image"><div className="relative max-w-xl aspect-square overflow-hidden rounded-2xl border border-line bg-wash">{originalImage ? <Image src={originalImage} alt="Original generated candidate" fill unoptimized className="object-contain"/> : <div className="flex size-full items-center justify-center text-sm text-muted">Unavailable</div>}</div></DetailSection>
    <DetailSection title="Generation Timeline"><ol className="overflow-hidden rounded-2xl border border-line bg-white">{events.map((event, index) => <li key={event.id} className={`grid gap-2 p-4 text-xs sm:grid-cols-[150px_120px_1fr] ${index ? "border-t border-line" : ""}`}><time className="text-muted">{new Date(event.timestamp).toLocaleString()}</time><strong className="capitalize">{event.kind.replaceAll("_", " ")}</strong><span>{event.message}</span></li>)}</ol></DetailSection>
  </div>;
}

function StoryBrief({ run }: { run: GenerationRun }) { const brief = run.story_brief; return <dl className="space-y-3 text-xs"><Fact label="Left" value={`${brief.title_left} — ${brief.left_action}`}/><Fact label="Right" value={`${brief.title_right} — ${brief.right_action}`}/><Fact label="Emotional insight" value={brief.emotional_insight}/><Fact label="Environment" value={`${brief.shared_environment} · ${brief.background_color} · ${brief.accent_color}`}/></dl>; }
function Fact({ label, value }: { label: string; value: string }) { return <div><dt className="font-bold uppercase tracking-[.12em] text-muted">{label}</dt><dd className="mt-1 leading-5">{value || "Not specified"}</dd></div>; }
function FactCard({ title, children }: { title: string; children: React.ReactNode }) { return <Card><CardContent className="p-5"><h2 className="mb-4 text-[11px] font-black uppercase tracking-[.16em] text-[#8c6325]">{title}</h2>{children}</CardContent></Card>; }
function DetailSection({ title, children }: { title: string; children: React.ReactNode }) { return <section><h2 className="mb-4 text-xl font-semibold">{title}</h2>{children}</section>; }
function CandidateCard({ candidate, selected, finalApproved }: { candidate: GenerationCandidate; selected: boolean; finalApproved: boolean }) { const image = assetUrl(candidate.final_asset_url || candidate.asset_url); return <Card className={selected ? "border-[#b58b24]" : ""}><div className="relative aspect-square bg-wash">{image ? <Image src={image} alt={`Candidate ${candidate.label}`} fill unoptimized className="object-contain"/> : <div className="flex size-full items-center justify-center text-xs text-muted">Unavailable</div>}</div><CardContent className="space-y-2 p-4"><div className="flex flex-wrap gap-2"><Badge>Candidate {candidate.label}</Badge>{candidate.recommended && <Badge>Recommended</Badge>}{selected && <Badge>Selected</Badge>}{finalApproved && <Badge>Final approved</Badge>}</div><p className="text-xs font-semibold">{candidate.model_power_label} · {candidate.model_display_name}</p><p className="text-[10px] text-muted">QA {candidate.qa_status}{candidate.repair_parent_id ? " · repaired" : ""}</p></CardContent></Card>; }
