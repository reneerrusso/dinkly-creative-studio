"use client";

import { Archive, BrainCircuit, Edit3 as Pencil, Search, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { AgentMemory } from "@/lib/types";

const sections = [
  ["all", "All memory"],
  ["creative_preference", "Creative preferences"],
  ["generation_learning", "Generation learnings"],
  ["prompt_learning", "Prompt learnings"],
  ["qa_learning", "QA learnings"],
  ["failure_pattern", "Failure patterns"],
  ["performance_learning", "Performance learnings"],
] as const;

const brainTargets = ["CREATIVE_BIBLE.md", "CHARACTER_BIBLE.md", "STYLE_GUIDE.md", "NANO_BANANA_RULES.md", "FAILURES.md"];

export default function MemoryPage() {
  const [records, setRecords] = useState<AgentMemory[]>([]);
  const [type, setType] = useState("all");
  const [query, setQuery] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<AgentMemory>();
  const [summary, setSummary] = useState("");
  const [target, setTarget] = useState("NANO_BANANA_RULES.md");
  const load = useCallback(async () => {
    const active = showInactive ? "&include_inactive=true" : "&active=true";
    const memoryType = type === "all" ? "" : `memory_type=${encodeURIComponent(type)}`;
    const separator = memoryType && active ? "&" : "";
    setRecords(await api<AgentMemory[]>(`/api/memory?${memoryType}${separator}${active.replace(/^&/, "")}`));
  }, [showInactive, type]);

  useEffect(() => { void load().catch(error => toast.error(error instanceof Error ? error.message : "Memory could not load")); }, [load]);
  const visible = useMemo(() => records.filter(record => JSON.stringify(record).toLowerCase().includes(query.toLowerCase())), [query, records]);

  async function save() {
    if (!editing) return;
    await api(`/api/memory/${editing.id}`, { method: "PUT", body: JSON.stringify({ summary }) });
    toast.success("Memory updated"); setEditing(undefined); await load();
  }
  async function deactivate(record: AgentMemory) {
    await api(`/api/memory/${record.id}/deactivate`, { method: "POST" });
    toast.success("Memory deactivated"); await load();
  }
  async function remove(record: AgentMemory) {
    if (!window.confirm("Permanently delete this memory record?")) return;
    await api(`/api/memory/${record.id}`, { method: "DELETE" });
    toast.success("Memory deleted"); await load();
  }
  async function propose(record: AgentMemory) {
    await api("/api/brain-update-proposals", { method: "POST", body: JSON.stringify({ memory_id: record.id, target_file: target }) });
    toast.success("Brain update proposal sent to Approvals");
  }

  return <div className="mx-auto max-w-6xl space-y-8 pb-16"><header><p className="text-[10px] font-bold uppercase tracking-[.2em] text-[#8c6325]">Evidence-linked intelligence</p><h1 className="mt-3 text-4xl font-semibold tracking-[-.045em]">DINKLY Memory</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-muted">Durable preferences and production learnings shared by web, Slack, scheduled work, and the Generation Engine. Chat context is not stored here unless it contains a lasting creative signal.</p></header>
    <Card><CardContent className="grid gap-3 p-5 md:grid-cols-[1fr_230px_auto]"><label className="relative"><Search className="absolute left-3 top-3 size-4 text-muted"/><Input aria-label="Search memory" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search evidence, rules, or sources" className="pl-9"/></label><Select aria-label="Memory section" value={type} onChange={event => setType(event.target.value)}>{sections.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</Select><Button type="button" variant={showInactive ? "default" : "outline"} onClick={() => setShowInactive(value => !value)}>Show inactive</Button></CardContent></Card>
    {visible.length === 0 ? <Card><CardContent className="py-16 text-center"><BrainCircuit className="mx-auto size-7 text-[#9b7521]"/><h2 className="mt-4 text-xl font-semibold">No matching durable memory</h2><p className="mt-2 text-sm text-muted">New records appear only when DINKLY has a lasting preference or evidence-backed learning.</p></CardContent></Card> : <div className="space-y-3">{visible.map(record => <Card key={record.id} className={!record.active ? "opacity-60" : undefined}><CardContent className="p-5"><div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between"><div className="min-w-0 flex-1"><div className="flex flex-wrap gap-2"><Badge>{record.memory_type.replaceAll("_", " ")}</Badge><Badge>{record.confidence} confidence</Badge><Badge>{record.active ? "active" : "inactive"}</Badge></div><p className="mt-4 text-sm leading-6">{record.summary}</p><dl className="mt-4 grid gap-2 text-[11px] text-muted sm:grid-cols-2"><div><dt className="font-bold uppercase tracking-wider">Source</dt><dd className="mt-1 break-all">{record.source_type}{record.source_id ? ` · ${record.source_id}` : ""}</dd></div><div><dt className="font-bold uppercase tracking-wider">Evidence</dt><dd className="mt-1 break-all">{record.evidence_ids.length ? record.evidence_ids.join(", ") : "No evidence IDs"}</dd></div></dl></div><div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => { setEditing(record); setSummary(record.summary); }}><Pencil className="size-3.5"/>Edit</Button>{record.active && <Button size="sm" variant="outline" onClick={() => void deactivate(record)}><Archive className="size-3.5"/>Deactivate</Button>}<Button size="sm" variant="ghost" onClick={() => void remove(record)}><Trash2 className="size-3.5"/>Delete</Button></div></div>{record.evidence_ids.length >= 2 && <div className="mt-5 flex flex-col gap-2 border-t border-line pt-4 sm:flex-row sm:items-center"><Select aria-label="Brain proposal target" value={target} onChange={event => setTarget(event.target.value)} className="sm:max-w-[260px]">{brainTargets.map(file => <option key={file}>{file}</option>)}</Select><Button size="sm" onClick={() => void propose(record)}>Propose permanent Brain rule</Button><span className="text-[10px] text-muted">Human approval is required before any permanent rule changes.</span></div>}</CardContent></Card>)}</div>}
    {editing && <Card className="border-[#d9b957]"><CardContent className="p-5"><p className="text-sm font-semibold">Edit memory</p><Textarea className="mt-3 min-h-28" value={summary} onChange={event => setSummary(event.target.value)}/><div className="mt-3 flex gap-2"><Button onClick={() => void save()}>Save</Button><Button variant="ghost" onClick={() => setEditing(undefined)}>Cancel</Button></div></CardContent></Card>}
  </div>;
}
