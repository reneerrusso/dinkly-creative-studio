"use client";

import Image from "next/image";
import { Brain, Check, ImageIcon, Lightbulb } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { ApprovalReviewDialog, type ApprovalDecision, type ApprovalKind, type ApprovalSelection } from "@/components/approval-review-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { API_URL, api } from "@/lib/api";
import type { AgentApprovals, DinklyAgentLearning, GenerationRun } from "@/lib/types";

export default function ApprovalsPage() {
  const [data, setData] = useState<AgentApprovals>();
  const [selection, setSelection] = useState<ApprovalSelection>();
  const [pending, setPending] = useState(new Set<string>());
  const load = useCallback(() => api<AgentApprovals>("/api/dinkly-agent/approvals").then(setData), []);
  useEffect(() => { load().catch(() => setData({ concepts: [], comics: [], brain_updates: [] })); const poll = window.setInterval(() => load().catch(() => undefined), 3000); return () => window.clearInterval(poll); }, [load]);

  async function decide(action: ApprovalDecision, itemType: ApprovalKind, itemId: string, notes?: string) {
    setPending(current => new Set(current).add(itemId));
    try {
      await api("/api/dinkly-agent/approvals", { method: "POST", body: JSON.stringify({ action, item_type: itemType, item_id: itemId, notes: notes || null, source_channel: "web", source_thread_id: "web-default" }) });
      toast.success("DINKLY received your decision");
      setSelection(undefined);
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Decision could not be saved");
    } finally {
      setPending(current => { const next = new Set(current); next.delete(itemId); return next; });
    }
  }

  const empty = data && !data.concepts.length && !data.comics.length && !data.brain_updates.length;
  return <div className="mx-auto max-w-6xl space-y-9 pb-16"><header><p className="text-[10px] font-bold uppercase tracking-[.2em] text-[#8c6325]">Your decisions</p><h1 className="mt-3 text-4xl font-semibold tracking-[-.045em]">Approvals</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-muted">Open any card to inspect the complete creative, model, QA, and evidence context without leaving this page.</p></header>
    {!data && <p className="text-sm text-muted">Loading DINKLY&apos;s review queue…</p>}
    {empty && <Card><CardContent className="py-16 text-center"><Check className="mx-auto size-7 text-emerald-700"/><h2 className="mt-4 text-xl font-semibold">Nothing is waiting</h2><p className="mt-2 text-sm text-muted">DINKLY will bring work here when it needs your decision.</p></CardContent></Card>}
    {data && data.concepts.length > 0 && <ApprovalSection icon={Lightbulb} title="Concepts" count={data.concepts.length}>{data.concepts.map(concept => <ConceptCard key={String(concept.id)} concept={concept} pending={pending.has(String(concept.id))} open={() => setSelection({ kind: "concept", item: concept })}/>)}</ApprovalSection>}
    {data && data.comics.length > 0 && <ApprovalSection icon={ImageIcon} title="Comics" count={data.comics.length}>{data.comics.map(run => <ComicCard key={run.id} run={run} pending={pending.has(run.id)} open={() => setSelection({ kind: "comic", item: run })}/>)}</ApprovalSection>}
    {data && data.brain_updates.length > 0 && <ApprovalSection icon={Brain} title="Brain updates" count={data.brain_updates.length}>{data.brain_updates.map(learning => <BrainCard key={learning.id} learning={learning} pending={pending.has(learning.id)} open={() => setSelection({ kind: "brain_update", item: learning })}/>)}</ApprovalSection>}
    <ApprovalReviewDialog selection={selection} open={Boolean(selection)} onOpenChange={open => { if (!open) setSelection(undefined); }} onDecision={decide}/>
  </div>;
}

function ConceptCard({ concept, pending, open }: { concept: Record<string, unknown>; pending: boolean; open: () => void }) { const title = String(concept.story_title || `${concept.title_left ?? "UNTITLED"} / ${concept.title_right ?? "WITH YOU"}`); return <Card className={pending ? "opacity-55" : "cursor-pointer transition hover:border-ink"} onClick={open}><CardContent className="flex flex-col justify-between gap-5 p-5 sm:flex-row sm:items-center"><div><Badge>{String(concept.format ?? "concept").replaceAll("_", " ")}</Badge><h3 className="mt-3 text-lg font-semibold">{title}</h3><p className="mt-2 max-w-2xl text-xs leading-5 text-muted">{String(concept.emotional_insight ?? concept.why_it_may_work ?? "A new DINKLY ordinary-life direction.")}</p></div><Button type="button" variant="outline" onClick={event => { event.stopPropagation(); open(); }}>Review details</Button></CardContent></Card>; }
function ComicCard({ run, pending, open }: { run: GenerationRun; pending: boolean; open: () => void }) { const candidate = run.candidates.find(item => item.recommended) ?? run.candidates.find(item => item.asset_url); return <Card className={pending ? "opacity-55" : "cursor-pointer transition hover:border-ink"} onClick={open}><CardContent className="grid gap-5 p-5 md:grid-cols-[180px_1fr]"><div className="relative aspect-square overflow-hidden rounded-2xl bg-wash">{candidate?.asset_url ? <Image src={`${API_URL}${candidate.asset_url}`} alt={run.concept_text} fill unoptimized className="object-contain"/> : <div className="flex size-full items-center justify-center text-xs text-muted">Image unavailable</div>}</div><div className="flex flex-col justify-between gap-5"><div><div className="flex flex-wrap items-center gap-2"><Badge>{candidate?.qa_status ?? "QA complete"}</Badge><Badge>{candidate?.model_power_label ?? run.model_selection_mode}</Badge></div><h3 className="mt-3 text-xl font-semibold">{run.concept_text}</h3><p className="mt-2 text-sm text-muted">{candidate ? `Candidate ${candidate.label} recommended · ${candidate.model_display_name}` : "Open the complete review context."}</p></div><Button type="button" variant="outline" className="self-start" onClick={event => { event.stopPropagation(); open(); }}>Review comic</Button></div></CardContent></Card>; }
function BrainCard({ learning, pending, open }: { learning: DinklyAgentLearning; pending: boolean; open: () => void }) { return <Card className={pending ? "opacity-55" : "cursor-pointer transition hover:border-ink"} onClick={open}><CardContent className="flex flex-col justify-between gap-5 p-5 sm:flex-row sm:items-center"><div><div className="flex gap-2"><Badge>{learning.confidence} confidence</Badge><Badge>{learning.learning_type.replaceAll("_", " ")}</Badge></div><p className="mt-3 max-w-3xl text-sm leading-6">{learning.statement}</p><p className="mt-2 text-[10px] text-muted">Supported by {learning.evidence_ids.length} evidence record{learning.evidence_ids.length === 1 ? "" : "s"}.</p></div><Button type="button" variant="outline" onClick={event => { event.stopPropagation(); open(); }}>Review evidence</Button></CardContent></Card>; }
function ApprovalSection({ icon: Icon, title, count, children }: { icon: typeof Lightbulb; title: string; count: number; children: React.ReactNode }) { return <section><div className="mb-4 flex items-center gap-2"><Icon className="size-4 text-[#9b7521]"/><h2 className="text-xl font-semibold">{title}</h2><span className="rounded-full bg-[#f2df9d] px-2 py-0.5 text-[10px] font-bold">{count}</span></div><div className="space-y-3">{children}</div></section>; }
