"use client";

import Image from "next/image";
import { Check, Download, Edit3 as Pencil, RotateCcw, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { API_URL, api, downloadApiFile } from "@/lib/api";
import type { DinklyAgentLearning, GenerationCandidate, GenerationRun } from "@/lib/types";

export type ApprovalKind = "concept" | "comic" | "brain_update";
export type ApprovalDecision = "approve" | "pass" | "reject" | "fix" | "try_another" | "more_like_this" | "edit";
export interface ApprovalSelection { kind: ApprovalKind; item: Record<string, unknown> | GenerationRun | DinklyAgentLearning }

export function ApprovalReviewDialog({ selection, open, onOpenChange, onDecision }: {
  selection?: ApprovalSelection;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDecision: (action: ApprovalDecision, kind: ApprovalKind, id: string, notes?: string) => Promise<void>;
}) {
  const comicStyle = selection?.kind === "comic" ? { width: "90vw", maxWidth: "1100px", height: "min(820px, 90vh)", maxHeight: "90vh", overflow: "hidden" } : undefined;
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className={selection?.kind === "comic" ? "overflow-hidden p-0" : "p-0"} style={comicStyle}><DialogHeader className="sr-only"><DialogTitle>Approval review</DialogTitle><DialogDescription>Review the complete DINKLY production context before deciding.</DialogDescription></DialogHeader>{selection?.kind === "comic" && <ComicReview run={selection.item as GenerationRun} onDecision={onDecision}/>} {selection?.kind === "concept" && <ConceptReview concept={selection.item as Record<string, unknown>} onDecision={onDecision}/>} {selection?.kind === "brain_update" && <BrainReview learning={selection.item as DinklyAgentLearning} onDecision={onDecision}/>}</DialogContent></Dialog>;
}

function ComicReview({ run, onDecision }: { run: GenerationRun; onDecision: ApprovalReviewDialogProps["onDecision"] }) {
  const initial = run.candidates.find(item => item.id === run.selected_candidate_id) ?? run.candidates.find(item => item.recommended) ?? run.candidates[0];
  const [candidateId, setCandidateId] = useState(initial?.id ?? "");
  const [view, setView] = useState<"original" | "final">("final");
  const candidate = run.candidates.find(item => item.id === candidateId) ?? initial;
  useEffect(() => setCandidateId(initial?.id ?? ""), [initial?.id]);
  const original = candidate?.repair_parent_id ? run.candidates.find(item => item.id === candidate.repair_parent_id) : candidate;
  const imageUrl = view === "original" ? original?.asset_url : candidate?.final_asset_url ?? run.final_asset_url ?? candidate?.asset_url;
  const repairs = run.candidates.filter(item => item.repair_parent_id || item.repair_number);
  const findings = candidate?.qa_findings ?? [];
  const character = summarize(findings, "CHARACTER");
  const scene = summarize(findings, "SCENE");
  const prompt = summarize(findings, "TEXT", "PROP SCALE");

  async function decide(action: ApprovalDecision) {
    if (action === "approve" && candidate && candidate.id !== run.selected_candidate_id) {
      try { await api(`/api/generation-engine/candidates/${candidate.id}/select`, { method: "POST", body: JSON.stringify({ selected: true }) }); }
      catch (error) { toast.error(error instanceof Error ? error.message : "Candidate could not be selected"); return; }
    }
    await onDecision(action, "comic", run.id);
  }

  async function downloadArtwork() {
    const endpoint = view === "final" && run.status === "approved"
      ? `/api/generation-engine/runs/${run.id}/download/final?format=png`
      : `/api/generation-engine/runs/${run.id}/download/original?candidate_id=${encodeURIComponent(original?.id ?? candidate?.id ?? "")}`;
    try { await downloadApiFile(endpoint); }
    catch (error) { toast.error(error instanceof Error ? error.message : "Artwork download failed"); }
  }

  const status = run.status === "awaiting_human" ? "WAITING FOR APPROVAL" : run.status.replaceAll("_", " ").toUpperCase();

  return <div className="grid h-full min-h-0 grid-rows-[minmax(0,1fr)_auto]">
    <div className="grid min-h-0 overflow-y-auto lg:grid-cols-[55%_45%] lg:overflow-hidden">
      <section className="flex min-h-[520px] min-w-0 flex-col bg-[#f6f0e3] p-5 sm:p-7 lg:min-h-0">
        <p className="text-[10px] font-black uppercase tracking-[.18em] text-[#8c6325]">Comic approval</p>
        <div className="mt-4 flex gap-2" aria-label="Candidates">{run.candidates.map(item => <button key={item.id} type="button" aria-label={`Candidate ${item.label}`} onClick={() => setCandidateId(item.id)} className={`flex size-9 items-center justify-center rounded-full border text-xs font-black transition ${item.id === candidate?.id ? "border-[#d4ad34] bg-[#e7c85d] text-black" : "border-black/15 bg-white/65 text-[#6d665a] hover:border-black/35"}`}>{item.label}</button>)}</div>
        <div className="relative mt-4 min-h-[360px] flex-1 overflow-hidden rounded-[22px] border border-black/[.08] bg-white/70">{imageUrl ? <Image src={`${API_URL}${imageUrl}`} alt={`Candidate ${candidate?.label ?? "preview"}`} fill unoptimized className="object-contain p-2"/> : <div className="flex size-full min-h-[360px] items-center justify-center text-sm text-muted">Preview unavailable</div>}</div>
        <div className="mt-4 inline-flex w-fit rounded-full border border-black/10 bg-white p-1" aria-label="Artwork view"><button type="button" onClick={() => setView("original")} className={`rounded-full px-4 py-2 text-xs font-bold ${view === "original" ? "bg-[#171713] text-white" : "text-muted"}`}>Original</button><button type="button" onClick={() => setView("final")} className={`rounded-full px-4 py-2 text-xs font-bold ${view === "final" ? "bg-[#e7c85d] text-black" : "text-muted"}`}>Final 80/20</button></div>
      </section>
      <aside className="min-w-0 space-y-5 bg-white p-5 sm:p-7 lg:overflow-y-auto lg:pr-9">
        <div className="pr-6"><p className="text-[10px] font-black uppercase tracking-[.16em] text-[#8c6325]">{status}</p><h2 className="mt-2 break-words text-2xl font-semibold leading-tight">{run.concept_text}</h2></div>
        <Detail label="Story brief" value={`${run.story_brief.left_action}\n${run.story_brief.right_action}`}/>
        <div className="grid grid-cols-2 gap-3"><Metric label="Model" value={`${candidate?.model_power_label ?? "MODEL"} · ${candidate?.model_display_name ?? run.selected_model_info?.display_name ?? "Unknown"}`}/><Metric label="Runtime" value={duration(candidate?.runtime_ms ?? run.runtime_ms)}/><Metric label="Generated" value={formatDate(run.completed_at ?? run.started_at)}/><Metric label="Candidate" value={candidate ? `Candidate ${candidate.label}` : "None"}/></div>
        <QaBlock title="QA" value={concise(candidate?.qa_summary ?? "QA unavailable")}/>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2"><QaBlock title="Character consistency" value={character}/><QaBlock title="Scene accuracy" value={scene}/></div>
        <div><p className="detail-label">Repairs</p>{repairs.length ? <ul className="mt-2 space-y-2 text-xs leading-5 text-muted">{repairs.map(item => <li key={item.id}>Candidate {item.label} repaired from {item.repair_parent_id ?? "an earlier candidate"}.</li>)}</ul> : <p className="mt-2 text-xs text-muted">No repairs.</p>}</div>
        <details className="rounded-xl border border-line bg-white p-4"><summary className="cursor-pointer text-xs font-bold text-[#76591d]">View full QA details</summary><div className="mt-4 space-y-3"><Detail label="QA summary" value={candidate?.qa_summary ?? "QA unavailable"}/><Detail label="Prompt alignment" value={prompt}/></div></details>
      </aside>
    </div>
    <footer className="z-10 flex shrink-0 flex-wrap items-center gap-2 border-t border-line bg-white px-5 py-3 sm:px-7">
      <Button onClick={() => void decide("approve")}><Check className="size-4"/>Approve Comic</Button>
      <Button variant="outline" onClick={() => void decide("fix")}>Fix Issues</Button>
      <Button variant="outline" onClick={() => void decide("try_another")}><RotateCcw className="size-4"/>Try Another</Button>
      <Button variant="ghost" onClick={() => void decide("reject")}><X className="size-4"/>Reject</Button>
      {imageUrl && <Button type="button" variant="ghost" className="sm:ml-auto" onClick={() => void downloadArtwork()}><Download className="size-4"/>Download</Button>}
    </footer>
  </div>;
}

function ConceptReview({ concept, onDecision }: { concept: Record<string, unknown>; onDecision: ApprovalReviewDialogProps["onDecision"] }) {
  const id = String(concept.id);
  const [editing, setEditing] = useState(false);
  const [notes, setNotes] = useState(String(concept.why_it_may_work ?? ""));
  const title = String(concept.story_title || `${concept.title_left ?? "UNTITLED"} / ${concept.title_right ?? "WITH YOU"}`);
  return <div className="p-6 sm:p-8"><p className="text-[10px] font-bold uppercase tracking-[.18em] text-[#8c6325]">Concept approval</p><h2 className="mt-2 text-3xl font-semibold">{title}</h2><div className="mt-6 grid gap-5 md:grid-cols-2"><Detail label="Format" value={String(concept.format ?? "concept").replaceAll("_", " ")}/><Detail label="Background" value={`${concept.background_color ?? "Not specified"} · Accent: ${concept.accent_color ?? "Not specified"}`}/><Detail label="Left scene" value={String(concept.left_action ?? concept.left_scene ?? "Not specified")}/><Detail label="Right scene" value={String(concept.right_action ?? concept.right_scene ?? "Not specified")}/><Detail label="Props" value={list(concept.left_props, concept.right_props, concept.props)}/><Detail label="Why it may work" value={String(concept.why_it_may_work ?? concept.emotional_insight ?? "Not specified")}/><Detail label="Relevant learning / preference signals" value={list(concept.social_learning_ids, concept.preference_matches)}/></div>{editing && <div className="mt-5"><p className="detail-label">Edit why it may work</p><Textarea aria-label="Concept revision" className="mt-2" value={notes} onChange={event => setNotes(event.target.value)}/></div>}<div className="mt-7 flex flex-wrap gap-2"><Button onClick={() => void onDecision("approve", "concept", id)}><Check className="size-4"/>Approve</Button><Button variant="ghost" onClick={() => void onDecision("pass", "concept", id)}>Pass</Button>{editing ? <Button variant="outline" onClick={() => void onDecision("edit", "concept", id, notes)}><Pencil className="size-4"/>Save Edit</Button> : <Button variant="outline" onClick={() => setEditing(true)}><Pencil className="size-4"/>Edit</Button>}<Button variant="outline" onClick={() => void onDecision("more_like_this", "concept", id)}><Sparkles className="size-4"/>More Like This</Button></div></div>;
}

function BrainReview({ learning, onDecision }: { learning: DinklyAgentLearning; onDecision: ApprovalReviewDialogProps["onDecision"] }) {
  const [editing, setEditing] = useState(false);
  const [statement, setStatement] = useState(learning.statement);
  const memory = useMemo(() => memoryFile(learning.learning_type), [learning.learning_type]);
  return <div className="p-6 sm:p-8"><p className="text-[10px] font-bold uppercase tracking-[.18em] text-[#8c6325]">Brain update approval</p><h2 className="mt-2 text-3xl font-semibold">Proposed learning</h2><div className="mt-6 space-y-5"><Detail label="Proposed learning" value={learning.statement}/><Detail label="Evidence" value={learning.evidence_ids.length ? learning.evidence_ids.join(", ") : "No evidence IDs recorded"}/><div className="grid gap-3 sm:grid-cols-3"><Metric label="Confidence" value={learning.confidence}/><Metric label="Source generations" value={String(learning.evidence_ids.length)}/><Metric label="Memory affected" value={memory}/></div>{editing && <div><p className="detail-label">Revised learning</p><Textarea aria-label="Brain learning revision" className="mt-2" value={statement} onChange={event => setStatement(event.target.value)}/></div>}</div><div className="mt-7 flex flex-wrap gap-2"><Button onClick={() => void onDecision("approve", "brain_update", learning.id)}><Check className="size-4"/>Approve</Button><Button variant="ghost" onClick={() => void onDecision("reject", "brain_update", learning.id)}>Reject</Button>{editing ? <Button variant="outline" onClick={() => void onDecision("edit", "brain_update", learning.id, statement)}><Pencil className="size-4"/>Save Edit</Button> : <Button variant="outline" onClick={() => setEditing(true)}><Pencil className="size-4"/>Edit</Button>}</div></div>;
}

type ApprovalReviewDialogProps = React.ComponentProps<typeof ApprovalReviewDialog>;
function Detail({ label, value }: { label: string; value: string }) { return <div><p className="detail-label text-[10px] font-bold uppercase tracking-[.14em] text-muted">{label}</p><p className="mt-2 whitespace-pre-line text-sm leading-6">{value || "Not specified"}</p></div>; }
function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-wash p-3"><p className="text-[9px] font-bold uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-xs font-semibold capitalize">{value}</p></div>; }
function QaBlock({ title, value }: { title: string; value: string }) { return <div className="rounded-xl border border-line p-4"><p className="text-[10px] font-bold uppercase tracking-[.13em] text-muted">{title}</p><p className="mt-2 text-xs leading-5">{value}</p></div>; }
function concise(value: string) { const clean = value.trim(); if (clean.length <= 180) return clean; const sentence = clean.match(/^.{1,180}?[.!?](?:\s|$)/)?.[0]; return sentence?.trim() ?? `${clean.slice(0, 177).trimEnd()}…`; }
function summarize(findings: GenerationCandidate["qa_findings"], ...categories: string[]) { const selected = findings.filter(item => categories.includes(item.category.toUpperCase())); if (!selected.length) return "No category-specific findings recorded."; const passes = selected.filter(item => item.status === "Pass").length; const issues = selected.filter(item => item.status !== "Pass"); return issues.length ? `${passes}/${selected.length} checks passed. ${issues.map(item => `${item.check}: ${item.detail}`).join(" ")}` : `${passes}/${selected.length} checks passed.`; }
function list(...values: unknown[]) { const flat = values.flatMap(value => Array.isArray(value) ? value : []).map(String); return flat.length ? flat.join(", ") : "None specified"; }
function duration(ms?: number | null) { return ms == null ? "Not recorded" : ms >= 1000 ? `${(ms / 1000).toFixed(1)} sec` : `${ms} ms`; }
function formatDate(value?: string | null) { return value ? new Date(value).toLocaleString() : "Not recorded"; }
function memoryFile(type: string) { return type.includes("prompt") ? "data/prompt_learnings.json" : type.includes("qa") || type.includes("failure") ? "data/qa_learnings.json" : type.includes("preference") ? "data/user_preferences.json" : "data/generation_learnings.json"; }
