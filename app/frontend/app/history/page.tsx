"use client";

import { AlertTriangle, Brain, CheckCircle2, Clock3, ImageIcon, Lightbulb, MessageCircle, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { AgentWorkHistory } from "@/lib/types";

export default function HistoryPage() {
  const [entries, setEntries] = useState<AgentWorkHistory[]>();
  useEffect(() => { api<AgentWorkHistory[]>("/api/dinkly-agent/history?limit=200").then(setEntries).catch(() => setEntries([])); }, []);
  const groups = useMemo(() => groupByDay(entries ?? []), [entries]);
  return <div className="mx-auto max-w-4xl space-y-8 pb-16"><header><p className="text-[10px] font-bold uppercase tracking-[.2em] text-[#8c6325]">Employee work log</p><h1 className="mt-3 text-4xl font-semibold tracking-[-.045em]">Activity</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-muted">What DINKLY created, reviewed, learned, and handed back—across the web workspace, Slack, and scheduled work.</p></header>
    {!entries && <p className="text-sm text-muted">Opening DINKLY&apos;s work log…</p>}
    {entries && !entries.length && <Card><CardContent className="py-16 text-center"><Clock3 className="mx-auto size-7 text-muted"/><h2 className="mt-4 text-xl font-semibold">No completed work yet</h2><p className="mt-2 text-sm text-muted">Assignments will appear here as DINKLY finishes them.</p></CardContent></Card>}
    {groups.map(group => <section key={group.label}><h2 className="mb-3 text-[10px] font-black uppercase tracking-[.2em] text-muted">{group.label}</h2><div className="overflow-hidden rounded-2xl border border-line bg-white">{group.entries.map((entry, index) => <WorkEntry key={entry.id} entry={entry} last={index === group.entries.length - 1}/>)}</div></section>)}
  </div>;
}

function WorkEntry({ entry, last }: { entry: AgentWorkHistory; last: boolean }) {
  const Icon = iconFor(entry.kind, entry.status);
  async function restart() { try { await api(`/api/dinkly-agent/tasks/${entry.id}/restart`, { method: "POST" }); toast.success("A new task was queued"); window.location.assign("/agent"); } catch (error) { toast.error(error instanceof Error ? error.message : "Could not restart task"); } }
  return <article className={`grid gap-3 p-5 sm:grid-cols-[90px_32px_1fr_auto] sm:items-start ${last ? "" : "border-b border-line"}`}><time className="text-xs font-semibold text-muted">{new Date(entry.timestamp).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</time><span className={`flex size-8 items-center justify-center rounded-full ${entry.status === "failed" || entry.status === "cancelled" ? "bg-red-100 text-red-700" : entry.status === "waiting_for_human" ? "bg-sky-100 text-sky-700" : "bg-[#f4e8bd] text-[#80631e]"}`}><Icon className="size-4"/></span><div><p className="text-sm font-semibold leading-6">{entry.message}</p><p className="mt-1 text-[10px] capitalize text-muted">{friendlyKind(entry.kind)} · from {entry.source_channel}</p>{entry.status === "cancelled" && <details className="mt-3 text-xs leading-6"><summary className="cursor-pointer font-semibold">Open</summary><dl className="mt-2 grid gap-1 rounded-xl bg-wash p-3"><div><dt className="inline font-semibold">Task: </dt><dd className="inline">{entry.task_instruction}</dd></div><div><dt className="inline font-semibold">Stopped at: </dt><dd className="inline">{entry.stopped_at ?? "Safe checkpoint"}</dd></div><div><dt className="inline font-semibold">Duration: </dt><dd className="inline">{formatDuration(entry.duration_seconds)}</dd></div><div><dt className="inline font-semibold">Completed artifacts: </dt><dd className="inline">{entry.completed_artifact_count ?? entry.artifact_ids.length}</dd></div></dl><Button className="mt-2" size="sm" variant="outline" onClick={() => void restart()}><RotateCcw className="size-3.5"/>Restart Task</Button></details>}</div><Badge>{entry.status === "waiting_for_human" ? "Waiting for you" : entry.status.toUpperCase()}</Badge></article>;
}

function groupByDay(entries: AgentWorkHistory[]) {
  const today = new Date();
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  const map = new Map<string, AgentWorkHistory[]>();
  entries.forEach(entry => { const date = new Date(entry.timestamp); const key = date.toDateString(); map.set(key, [...(map.get(key) ?? []), entry]); });
  return [...map.entries()].map(([key, values]) => { const date = new Date(key); const label = key === today.toDateString() ? "Today" : key === yesterday.toDateString() ? "Yesterday" : date.toLocaleDateString([], { month: "long", day: "numeric", year: date.getFullYear() === today.getFullYear() ? undefined : "numeric" }); return { label, entries: values }; });
}

function friendlyKind(kind: string) { return ({ generate_concepts: "Concept work", generate_comic: "Comic generation", repair_comic: "Artwork repair", review_comic: "Art review", learn: "Brain learning", feedback: "Preference memory", approval: "Human decision", brain_query: "Agent report" } as Record<string, string>)[kind] ?? "Assignment"; }
function iconFor(kind: string, status: string) { if (status === "cancelled" || status === "failed") return AlertTriangle; return ({ generate_concepts: Lightbulb, generate_comic: ImageIcon, repair_comic: ImageIcon, review_comic: CheckCircle2, learn: Brain, feedback: Brain, approval: CheckCircle2, brain_query: MessageCircle } as Record<string, typeof Clock3>)[kind] ?? Clock3; }
function formatDuration(seconds?: number | null) { if (seconds == null) return "Not recorded"; return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`; }
