"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, ArrowRight, Check, Edit3, MessageCircle, RefreshCw, Search, Sparkles, Trash2, X } from "lucide-react";
import { Suspense, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { AgentAvatar } from "@/components/agent-avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { API_URL, api } from "@/lib/api";
import { agentById } from "@/lib/agents";
import { cn } from "@/lib/utils";

type Format = "with_you" | "before_after" | "five_story";
type View = "today" | "queue" | "used" | "passed" | "batches" | "preferences";

interface Beat { title: string; scene: string; setting: string; props: string[]; emotion: string }
interface ContentConcept {
  id: string; batch_id: string; format: Format; status: string; slot: number; title_left?: string; title_right?: string; story_title?: string;
  left_action?: string; left_setting?: string; left_props: string[]; right_action?: string; right_setting?: string; right_props: string[];
  background_color: string; accent_color: string; emotional_insight?: string; emotional_premise?: string; why_it_may_work: string;
  timely_signal?: string; preference_matches: string[]; social_learning_ids: string[]; execution_risks: string[]; comics: Beat[]; final_payoff?: string;
  prompt_ids: string[]; development_fixture: boolean;
}
interface Preference { id: string; preference_type: string; topic: string; value: string; strength: string; source: string; confidence: string; active: boolean; updated_at: string }
interface AgentRun { id: string; status: string; kind: string; created_at: string; completed_at?: string; error?: string }
interface AgentEvent { id: string; message: string; timestamp: string; kind: string; level: string }
interface ContentState {
  provider_configured: boolean; provider_name: string; today: string; today_batches: Array<Record<string, any>>; batches: Array<Record<string, any>>; today_concepts: ContentConcept[];
  production_queue: ContentConcept[]; passed: ContentConcept[]; used_storylines: Array<Record<string, any>>; preferences: Preference[];
  chat: Array<{ id: string; role: string; message: string; created_at: string }>;
  settings: { generate_daily_automatically: boolean; run_time: string; timezone: string; schedule_days: "every_day" | "weekdays"; catch_up_on_wake: boolean; catch_up_on_start: boolean; generate_on_start: boolean; enable_paid_model_calls: boolean; maximum_automatic_batch_cost: number; maximum_manual_batch_cost: number; daily_model_budget: number; monthly_model_budget: number; last_scheduler_check?: string | null };
  scheduler: { last_successful_run?: string | null; next_run: string; last_status: string; last_run_id?: string | null };
  background_agent: { installed: boolean; running: boolean; status: string };
  latest_run?: AgentRun;
}

const formatLabels: Record<Format, string> = { with_you: "WITH YOU", before_after: "BEFORE / AFTER", five_story: "5-COMIC STORIES" };
const views: Array<[View, string]> = [["today", "Today"], ["queue", "Ready to Make"], ["used", "Used"], ["passed", "Passed"], ["batches", "Past Batches"], ["preferences", "Preferences"]];

export default function ConceptGeneratorPage() {
  return <Suspense fallback={<div className="p-8 text-sm text-muted">Opening the daily creative desk…</div>}><ContentDesk /></Suspense>;
}

function ContentDesk() {
  const params = useSearchParams();
  const [state, setState] = useState<ContentState>();
  const [view, setView] = useState<View>((params.get("view") as View) || "today");
  const [format, setFormat] = useState<Format>("with_you");
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [activityOpen, setActivityOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [chat, setChat] = useState("");
  const [regenerateOpen, setRegenerateOpen] = useState(false);
  const [promptBundle, setPromptBundle] = useState<Array<{ title: string; prompt: string; comic_number?: number }>>([]);
  const agent = agentById("concept-generator")!;

  const load = useCallback(async () => setState(await api<ContentState>("/api/concept-generator")), []);
  useEffect(() => { load().catch(error => toast.error(error.message)); }, [load]);
  useEffect(() => {
    const run = state?.latest_run;
    if (!run || (run.status !== "Running" && !activityOpen)) return;
    const source = new EventSource(`${API_URL}/api/agent-runs/${run.id}/events`);
    const receive = (event: MessageEvent) => {
      const item = JSON.parse(event.data) as AgentEvent;
      setEvents(current => current.some(existing => existing.id === item.id) ? current : [...current, item]);
      if (item.kind === "complete" || item.kind === "failed") { source.close(); void load(); }
    };
    ["run", "scheduler", "manual", "provider", "preflight", "prepare", "research", "build_brief", "generate_with_you", "generate_before_after", "generate_five_story", "generated", "validation_retry", "deduplicate", "score", "refine", "select_finalists", "save_batch", "await_review", "complete", "failed"].forEach(kind => source.addEventListener(kind, receive));
    return () => source.close();
  }, [state?.latest_run?.id, state?.latest_run?.status, activityOpen, load]);

  const candidates = state?.today_concepts.filter(item => item.format === format) ?? [];
  const approved = (state?.production_queue.filter(item => item.format === format && state.today_batches.some(batch => batch.id === item.batch_id)).length ?? 0)
    + (state?.used_storylines.filter(item => item.format === format && state.today_batches.some(batch => batch.id === item.source_batch)).length ?? 0);
  const status = statusLabel(state?.latest_run, Boolean(state?.provider_configured), events[events.length - 1]?.kind);

  async function mutate(path: string, init: RequestInit = { method: "POST", body: "{}" }) {
    setBusy(true);
    try { const result = await api<any>(path, init); await load(); return result; }
    catch (error) { toast.error(error instanceof Error ? error.message : "Concept Generator could not complete that action"); }
    finally { setBusy(false); }
  }

  async function generate(mode = "primary") {
    const result = await mutate("/api/concept-generator/batches", { method: "POST", body: JSON.stringify({ mode }) });
    if (result?.run) { setEvents([]); setActivityOpen(true); toast.success("Concept Generator started today’s batch"); }
  }

  async function sendChat() {
    if (!chat.trim()) return;
    const message = chat; setChat("");
    const result = await mutate("/api/concept-generator/chat", { method: "POST", body: JSON.stringify({ message }) });
    if (result?.reply) toast.success("Creative preference remembered");
  }

  async function prompt(concept: ContentConcept) {
    const result = await mutate(`/api/concept-generator/concepts/${concept.id}/prompt-handoff`);
    if (!result) return;
    if (result.kind === "single") window.location.href = result.href;
    else { setPromptBundle(result.prompts); setView("queue"); toast.success("Five continuity-locked prompts are ready"); }
  }

  async function approveConcept(conceptId: string) {
    const result = await mutate(`/api/concept-generator/concepts/${conceptId}/approve`);
    if (result?.story_library_id) toast.success("Concept approved and added to Story Library");
  }

  async function fixBackgroundAgent() {
    const action = state?.background_agent.installed ? "restart" : "install";
    const result = await mutate(`/api/concept-generator/background-agent/${action}`);
    if (result?.running) toast.success("Background agent is running");
    else if (result) toast.success("Background agent started; waiting for its first heartbeat");
  }

  if (!state) return <div className="p-8 text-sm text-muted">Concept Generator is opening the DINKLY Brain…</div>;

  return <div className="mx-auto max-w-6xl space-y-5 pb-16">
    <section className="rounded-[24px] border border-black/[0.06] bg-white p-4 shadow-[0_18px_55px_-48px_rgba(30,27,20,.6)]">
      <button type="button" onClick={() => setActivityOpen(value => !value)} className="flex w-full items-center gap-4 text-left">
        <AgentAvatar agentId={agent.id} size="md" showStatus status={status.live ? "working" : "online"} className={cn(status.live && "animate-[pulse_3s_ease-in-out_infinite]")}/>
        <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h1 className="font-semibold">Concept Generator</h1><span className={cn("rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide", status.live ? "bg-emerald-50 text-emerald-800" : "bg-wash text-muted")}>{status.label}</span></div><p className="mt-1 truncate text-sm text-muted">{status.message}</p></div>
        <div className="hidden grid-cols-2 gap-6 text-right sm:grid"><RunTime label="Last run" value={state.scheduler.last_successful_run ?? (state.latest_run?.status === "Completed" ? state.latest_run.completed_at ?? state.latest_run.created_at : null)}/><RunTime label="Next run" value={state.settings.generate_daily_automatically ? state.scheduler.next_run : null}/></div>
      </button>
      <div className="mt-3 flex items-center justify-between border-t border-line pt-3 text-[11px] text-muted"><span>{state.scheduler.last_status === "Succeeded" && state.scheduler.last_successful_run ? `Today’s batch was generated automatically at ${new Date(state.scheduler.last_successful_run).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}.` : "Automatic runs are recorded even while the app is closed."}</span><button type="button" className="font-semibold text-ink underline underline-offset-4" onClick={() => setActivityOpen(value => !value)}>View work {activityOpen ? "↑" : "↓"}</button></div>
      {activityOpen && <div className="mt-4 max-h-64 space-y-2 overflow-auto border-t border-line pt-4">{events.length ? events.map(event => <div key={event.id} className="flex items-start gap-3 text-xs leading-5"><AgentAvatar agentId="concept-generator" size="xs" status={status.live ? "working" : "online"}/><p>{event.message}</p><time className="ml-auto shrink-0 text-[10px] text-muted">{new Date(event.timestamp).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</time></div>) : <p className="text-xs text-muted">No saved events for the latest run yet.</p>}</div>}
    </section>

    {state.settings.generate_daily_automatically && !state.background_agent.running && <section className="flex flex-col gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 sm:flex-row sm:items-center"><AlertTriangle className="size-5 shrink-0 text-amber-700"/><p className="flex-1 text-sm font-semibold text-amber-950">Automatic 8:00 AM generation is enabled, but the background agent is not running.</p><Button size="sm" onClick={fixBackgroundAgent} disabled={busy}>Fix Background Agent</Button></section>}

    <section className="rounded-2xl border border-black/[0.06] bg-white p-4">
      <div className="flex items-center gap-2 text-xs font-semibold"><MessageCircle className="size-4"/>Tell Concept Generator what you want</div>
      <div className="mt-3 flex gap-2"><Input value={chat} onChange={event => setChat(event.target.value)} onKeyDown={event => { if (event.key === "Enter") void sendChat(); }} placeholder="Tell Concept Generator what you want more or less of…"/><Button aria-label="Send feedback" onClick={sendChat} disabled={busy || !chat.trim()}><ArrowRight className="size-4"/></Button></div>
      {state.chat.length > 0 && <div className="mt-3 space-y-2">{state.chat.slice(-4).map(item => <div key={item.id} className={cn("flex items-start gap-2 rounded-xl px-3 py-2 text-xs leading-5", item.role === "user" ? "ml-10 bg-wash" : "mr-6 bg-[#f6f1e7]")}>{item.role !== "user" && <AgentAvatar agentId="concept-generator" size="xs"/>}<p>{item.message}</p></div>)}</div>}
    </section>

    <nav aria-label="Concept Generator views" className="flex gap-1 overflow-x-auto rounded-xl border border-line bg-white p-1">{views.map(([key, label]) => <button key={key} type="button" onClick={() => setView(key)} className={cn("whitespace-nowrap rounded-lg px-3 py-2 text-xs font-semibold", view === key ? "bg-ink text-white" : "text-muted hover:bg-wash")}>{label}</button>)}</nav>

    {view === "today" && <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-muted">Today</p><h2 className="mt-1 text-2xl font-semibold tracking-[-.03em]">{new Date(`${state.today}T12:00:00`).toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}</h2></div>{state.today_batches.length > 0 && <Button variant="outline" onClick={() => setRegenerateOpen(true)} disabled={busy || !state.provider_configured}><RefreshCw className="size-4"/>Regenerate today’s batch</Button>}</div>
      {regenerateOpen && <div className="rounded-2xl border border-mustard/40 bg-mustard/10 p-4"><p className="text-sm font-semibold">Regenerate today’s batch?</p><p className="mt-1 text-xs text-muted">Approved concepts are always preserved.</p><div className="mt-3 flex flex-wrap gap-2"><Button size="sm" onClick={() => { setRegenerateOpen(false); void generate("replace_unreviewed"); }}>Replace unreviewed concepts</Button><Button size="sm" variant="outline" onClick={() => { setRegenerateOpen(false); void generate("supplemental"); }}>Create supplemental batch</Button><Button size="sm" variant="ghost" onClick={() => setRegenerateOpen(false)}>Cancel</Button></div></div>}
      {state.today_batches.length === 0 ? <EmptyToday configured={state.provider_configured} onGenerate={() => generate()} busy={busy}/> : <>
        <div className="grid grid-cols-3 gap-1 rounded-xl bg-[#ebe8df] p-1">{(Object.keys(formatLabels) as Format[]).map(key => <button key={key} type="button" onClick={() => setFormat(key)} className={cn("rounded-lg px-2 py-2.5 text-[10px] font-bold tracking-wide sm:text-xs", format === key ? "bg-white shadow-sm" : "text-muted")}>{formatLabels[key]} <span className="ml-1">{state.today_concepts.filter(item => item.format === key).length}</span></button>)}</div>
        <div className="flex items-center justify-between"><p className="text-xs text-muted">Review one format at a time. Advanced evidence stays behind Why this?</p><span className="rounded-full bg-mustard/20 px-3 py-1 text-xs font-semibold">Approved {approved} / 5</span></div>
        {candidates.length ? <div className="grid gap-4 lg:grid-cols-2">{candidates.map(concept => <ConceptCard key={concept.id} concept={concept} busy={busy} onApprove={() => void approveConcept(concept.id)} onPass={reason => mutate(`/api/concept-generator/concepts/${concept.id}/pass`, { method: "POST", body: JSON.stringify({ reason }) })} onEdit={changes => mutate(`/api/concept-generator/concepts/${concept.id}`, { method: "PATCH", body: JSON.stringify({ changes }) })}/>)}</div> : <Card><CardContent className="p-8 text-center text-sm text-muted">You reviewed every active concept in this format. Approved ideas are waiting in Ready to Make and saved in the Story Library.</CardContent></Card>}
      </>}
    </section>}

    {view === "queue" && <Queue concepts={state.production_queue} promptBundle={promptBundle} busy={busy} onPrompt={prompt} onUsed={id => mutate(`/api/concept-generator/concepts/${id}/used`)} onRemove={id => mutate(`/api/concept-generator/concepts/${id}/queue`, { method: "DELETE" })} onEdit={(id, changes) => mutate(`/api/concept-generator/concepts/${id}`, { method: "PATCH", body: JSON.stringify({ changes }) })}/>} 
    {view === "used" && <Used records={state.used_storylines} onVariation={id => mutate(`/api/concept-generator/used/${id}/variation`)}/>} 
    {view === "passed" && <SimpleList title="Passed Concepts" concepts={state.passed}/>} 
    {view === "batches" && <Batches batches={state.batches}/>} 
    {view === "preferences" && <Preferences state={state} busy={busy} reload={load}/>} 
  </div>;
}

function ConceptCard({ concept, busy, onApprove, onPass, onEdit }: { concept: ContentConcept; busy: boolean; onApprove: () => void; onPass: (reason?: string) => void; onEdit: (changes: Record<string, unknown>) => void }) {
  const [why, setWhy] = useState(false); const [passing, setPassing] = useState(false); const [editing, setEditing] = useState(false); const [left, setLeft] = useState(concept.left_action ?? concept.emotional_premise ?? ""); const [right, setRight] = useState(concept.right_action ?? concept.final_payoff ?? "");
  const title = concept.story_title ?? `${concept.title_left} / ${concept.title_right}`;
  return <article className="relative overflow-hidden rounded-[22px] border border-black/[0.065] bg-white p-5 shadow-[0_22px_50px_-48px_rgba(30,27,20,.65)]">
    <div className="absolute inset-x-0 top-0 h-1" style={{ backgroundColor: pastel(concept.background_color) }}/><div className="flex items-start justify-between gap-3"><div><p className="text-[9px] font-bold uppercase tracking-[.16em] text-muted">{formatLabels[concept.format]}</p><h3 className="mt-2 whitespace-pre-line text-lg font-semibold leading-6">{title.replace(" / ", "\n")}</h3></div><span title={concept.background_color} className="size-6 shrink-0 rounded-full border border-black/10" style={{ backgroundColor: pastel(concept.background_color) }}/></div>
    {concept.format === "five_story" ? <div className="mt-4 space-y-2"><p className="text-sm leading-6 text-muted">{concept.emotional_premise}</p>{concept.comics.map((beat, index) => <div key={beat.title} className="grid grid-cols-[58px_1fr] gap-2 text-xs leading-5"><strong>Comic {index + 1}</strong><span>{beat.scene}</span></div>)}<p className="rounded-xl bg-wash p-3 text-xs font-semibold">{concept.final_payoff}</p></div> : <div className="mt-4 grid gap-3 sm:grid-cols-2"><Scene label="Left" text={concept.left_action ?? ""}/><Scene label="Right" text={concept.right_action ?? ""}/></div>}
    {editing && <div className="mt-4 space-y-2 rounded-xl bg-wash p-3"><Textarea aria-label="Edit first scene" value={left} onChange={event => setLeft(event.target.value)}/><Textarea aria-label="Edit second scene" value={right} onChange={event => setRight(event.target.value)}/><Button size="sm" onClick={() => { onEdit(concept.format === "five_story" ? { emotional_premise: left, final_payoff: right } : { left_action: left, right_action: right }); setEditing(false); }}>Save edit</Button></div>}
    {concept.format !== "five_story" && <p className="mt-4 text-xs leading-5 text-muted"><strong className="text-ink">Props:</strong> {Array.from(new Set([...concept.left_props, ...concept.right_props])).slice(0, 5).join(" · ")}</p>}
    <p className="mt-4 text-sm leading-6"><strong>Why it could work:</strong> {concept.why_it_may_work}</p>
    <button type="button" onClick={() => setWhy(value => !value)} className="mt-3 text-xs font-semibold underline underline-offset-4">Why this?</button>
    {why && <div className="mt-3 rounded-xl bg-[#f6f1e7] p-3 text-xs leading-5"><p><strong>DINKLY learning:</strong> {concept.social_learning_ids.length ? concept.social_learning_ids.join(", ") : "No unsupported performance claim; selected for brand fit and visual clarity."}</p><p><strong>Preference match:</strong> {concept.preference_matches.length ? concept.preference_matches.join(", ") : "No active preference was forced."}</p><p><strong>Timely signal:</strong> {concept.timely_signal || "Evergreen; no live trend was claimed."}</p><p><strong>Execution:</strong> {concept.execution_risks.join(" ")}</p></div>}
    {passing && <div className="mt-4 flex flex-wrap gap-1.5">{["Not relatable", "Too repetitive", "Too boring", "Too complicated", "Wrong tone", "Hard to visualize", "Too similar", "Don’t like the topic", "Other"].map(reason => <button key={reason} onClick={() => onPass(reason)} className="rounded-full border border-line px-2.5 py-1.5 text-[10px] font-semibold hover:bg-wash">{reason}</button>)}<button onClick={() => onPass()} className="px-2 text-[10px] text-muted">Skip reason</button></div>}
    <div className="sticky bottom-2 mt-5 flex flex-wrap gap-2 rounded-xl bg-white/95 pt-2 backdrop-blur"><Button size="sm" onClick={onApprove} disabled={busy}><Check className="size-4"/>Approve</Button><Button size="sm" variant="ghost" onClick={() => setPassing(value => !value)} disabled={busy}><X className="size-4"/>Pass</Button><Button size="sm" variant="ghost" onClick={() => setEditing(value => !value)}><Edit3 className="size-4"/>Edit</Button></div>
  </article>;
}

function Queue({ concepts, promptBundle, busy, onPrompt, onUsed, onRemove, onEdit }: { concepts: ContentConcept[]; promptBundle: Array<{ title: string; prompt: string; comic_number?: number }>; busy: boolean; onPrompt: (concept: ContentConcept) => void; onUsed: (id: string) => void; onRemove: (id: string) => void; onEdit: (id: string, changes: Record<string, unknown>) => void }) {
  return <section className="space-y-5"><div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-muted">Ready to make</p><h2 className="mt-1 text-2xl font-semibold">Production Queue</h2></div>{concepts.length ? (Object.keys(formatLabels) as Format[]).map(format => { const group = concepts.filter(item => item.format === format); return group.length ? <div key={format}><h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted">{formatLabels[format]}</h3><div className="space-y-2">{group.map(concept => <QueueItem key={concept.id} concept={concept} busy={busy} onPrompt={onPrompt} onUsed={onUsed} onRemove={onRemove} onEdit={onEdit}/>)}</div></div> : null; }) : <Empty title="Nothing is waiting yet" text="Approve any concept you like. It will move here immediately."/>}{promptBundle.length > 0 && <div className="space-y-3"><h3 className="text-lg font-semibold">Five-comic prompt set</h3>{promptBundle.map(item => <details key={item.comic_number} className="rounded-xl border border-line bg-white p-4"><summary className="cursor-pointer text-sm font-semibold">Comic {item.comic_number} Prompt · {item.title}</summary><pre className="mt-3 whitespace-pre-wrap text-xs leading-5">{item.prompt}</pre></details>)}</div>}</section>;
}

function QueueItem({ concept, busy, onPrompt, onUsed, onRemove, onEdit }: { concept: ContentConcept; busy: boolean; onPrompt: (concept: ContentConcept) => void; onUsed: (id: string) => void; onRemove: (id: string) => void; onEdit: (id: string, changes: Record<string, unknown>) => void }) { const [editing, setEditing] = useState(false); const [first, setFirst] = useState(concept.left_action ?? concept.emotional_premise ?? ""); const [second, setSecond] = useState(concept.right_action ?? concept.final_payoff ?? ""); return <div className="rounded-2xl border border-line bg-white p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center"><div className="min-w-0 flex-1"><p className="font-semibold">{concept.story_title ?? `${concept.title_left} / ${concept.title_right}`}</p><p className="mt-1 text-xs capitalize text-muted">{concept.status.replaceAll("_", " ")}</p></div><div className="flex flex-wrap gap-2"><Button size="sm" onClick={() => onPrompt(concept)} disabled={busy}><Sparkles className="size-4"/>Generate Prompt</Button><Button size="sm" variant="outline" onClick={() => setEditing(value => !value)}><Edit3 className="size-4"/>Edit Concept</Button><Button size="sm" variant="outline" onClick={() => onUsed(concept.id)}>Mark Used</Button><Button size="sm" variant="ghost" onClick={() => onRemove(concept.id)}><Trash2 className="size-4"/>Remove</Button></div></div>{editing && <div className="mt-3 grid gap-2 sm:grid-cols-2"><Textarea value={first} onChange={event => setFirst(event.target.value)}/><Textarea value={second} onChange={event => setSecond(event.target.value)}/><Button size="sm" onClick={() => { onEdit(concept.id, concept.format === "five_story" ? { emotional_premise: first, final_payoff: second } : { left_action: first, right_action: second }); setEditing(false); }}>Save queue edit</Button></div>}</div>; }

function Used({ records, onVariation }: { records: Array<Record<string, any>>; onVariation: (id: string) => void }) { const [query, setQuery] = useState(""); const filtered = records.filter(item => JSON.stringify(item.concept).toLowerCase().includes(query.toLowerCase())); return <section className="space-y-4"><div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-muted">Originality memory</p><h2 className="mt-1 text-2xl font-semibold">Used Storylines</h2></div><div className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"/><Input className="pl-9" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search used storylines…"/></div>{filtered.length ? filtered.map(item => <div key={item.id} className="flex items-center justify-between gap-4 rounded-2xl border border-line bg-white p-4"><div><p className="font-semibold">{item.concept.story_title ?? `${item.concept.title_left} / ${item.concept.title_right}`}</p><p className="mt-1 text-xs text-muted">Used {new Date(item.date_used).toLocaleDateString()} · {formatLabels[item.format as Format]}</p></div><Button size="sm" variant="outline" onClick={() => onVariation(item.id)}>Duplicate as variation</Button></div>) : <Empty title="No used storylines yet" text="When production begins, mark the concept Used. Concept Generator will protect it from silent regeneration."/>}</section>; }

function Preferences({ state, busy, reload }: { state: ContentState; busy: boolean; reload: () => Promise<void> }) { return <section className="space-y-5"><div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-muted">Brain · Content Preferences</p><h2 className="mt-1 text-2xl font-semibold">Concept Generator Preferences</h2><p className="mt-2 text-sm text-muted">Only DINKLY production preferences are stored. User feedback outranks behavior-based suggestions.</p></div><div className="flex items-center justify-between gap-4 rounded-2xl border border-line bg-white p-4"><div><p className="text-sm font-semibold">Daily automation</p><p className="mt-1 text-xs text-muted">{state.settings.generate_daily_automatically ? `Scheduled at ${state.settings.run_time} · ${state.settings.timezone}` : "Automatic generation is off."}</p></div><Button asChild size="sm" variant="outline"><Link href="/settings#concept-generator-scheduler">Scheduler Settings</Link></Button></div>{state.preferences.length ? state.preferences.map(item => <PreferenceRow key={item.id} item={item} busy={busy} reload={reload}/>) : <Empty title="No preferences yet" text="Tell Concept Generator what you want more or less of. Your feedback will appear here."/>}</section>; }

function PreferenceRow({ item, busy, reload }: { item: Preference; busy: boolean; reload: () => Promise<void> }) { const [editing, setEditing] = useState(false); const [topic, setTopic] = useState(item.topic); const [strength, setStrength] = useState(item.strength); async function patch(changes: Record<string, unknown>) { await api(`/api/concept-generator/preferences/${item.id}`, { method: "PATCH", body: JSON.stringify(changes) }); await reload(); } async function remove() { await api(`/api/concept-generator/preferences/${item.id}`, { method: "DELETE" }); await reload(); } const source = item.source === "content_agent_chat" || item.source === "concept_generator_chat" ? "Concept Generator chat" : item.source.replaceAll("_", " "); return <div className="rounded-2xl border border-line bg-white p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center"><div className="min-w-0 flex-1"><p className="text-[9px] font-bold uppercase tracking-wide text-muted">{item.preference_type.replaceAll("_", " ")} · {item.strength}</p><p className="mt-1 font-semibold">{item.topic}</p><p className="mt-1 text-xs text-muted">{source} · {item.confidence} confidence{!item.active && " · inactive"}</p></div><Button size="sm" variant="outline" onClick={() => setEditing(value => !value)}><Edit3 className="size-4"/>Edit</Button><Button size="sm" variant="outline" onClick={() => patch({ active: !item.active })} disabled={busy}>{item.active ? "Deactivate" : "Activate"}</Button><Button size="sm" variant="ghost" onClick={remove}><Trash2 className="size-4"/>Delete</Button></div>{editing && <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_160px_auto]"><Input value={topic} onChange={event => setTopic(event.target.value)}/><select value={strength} onChange={event => setStrength(event.target.value)} className="h-10 rounded-xl border border-line bg-white px-3 text-sm"><option>weak</option><option>medium</option><option>strong</option></select><Button size="sm" onClick={() => { void patch({ topic, value: topic, strength }); setEditing(false); }}>Save</Button></div>}</div>; }

function EmptyToday({ configured, onGenerate, busy }: { configured: boolean; onGenerate: () => void; busy: boolean }) { return <Empty title="No concepts have been generated today." text={configured ? "Concept Generator is ready to build the morning batch." : "Concept Generator needs an AI provider to create new concepts. Existing stories and prior batches remain available."} actions={configured ? <Button onClick={onGenerate} disabled={busy}><Sparkles className="size-4"/>Generate Today’s Concepts</Button> : <div className="flex flex-wrap justify-center gap-2"><Button asChild variant="outline"><Link href="/story-library">Browse existing Story Library</Link></Button><Button asChild><Link href="/settings">Configure provider</Link></Button></div>}/>; }
function Empty({ title, text, actions }: { title: string; text: string; actions?: React.ReactNode }) { return <Card><CardContent className="p-9 text-center"><p className="font-semibold">{title}</p><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted">{text}</p>{actions && <div className="mt-5">{actions}</div>}</CardContent></Card>; }
function Scene({ label, text }: { label: string; text: string }) { return <div className="rounded-xl bg-wash p-3"><p className="text-[9px] font-bold uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-xs leading-5">{text}</p></div>; }
function SimpleList({ title, concepts }: { title: string; concepts: ContentConcept[] }) { return <section className="space-y-3"><h2 className="text-2xl font-semibold">{title}</h2>{concepts.length ? concepts.map(item => <div key={item.id} className="rounded-2xl border border-line bg-white p-4"><p className="font-semibold">{item.story_title ?? `${item.title_left} / ${item.title_right}`}</p><p className="mt-1 text-xs text-muted">{formatLabels[item.format]} · preserved in history</p></div>) : <Empty title="Nothing here yet" text="Passed concepts remain available without cluttering today’s review."/>}</section>; }
function Batches({ batches }: { batches: Array<Record<string, any>> }) { return <section className="space-y-3"><h2 className="text-2xl font-semibold">Past Batches</h2>{batches.length ? batches.map(item => <div key={item.id} className="rounded-2xl border border-line bg-white p-4"><div className="flex justify-between gap-3"><p className="font-semibold">{new Date(`${item.date}T12:00:00`).toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" })}</p><span className="text-xs capitalize text-muted">{item.status.replaceAll("_", " ")}</span></div>{item.generation_source === "catch_up" && <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">Scheduled {item.scheduled_for ? new Date(item.scheduled_for).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "8:00 AM"} · Started {new Date(item.created_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} · Mac unavailable at scheduled time.</p>}<p className="mt-2 text-xs leading-5 text-muted">{item.source_summary}</p><p className="mt-2 text-xs">{item.with_you_count + item.before_after_count + item.five_story_count} finalists · {item.approved_count} approved · {item.used_count} used</p></div>) : <Empty title="No past batches" text="Daily and supplemental batches will remain browsable here."/>}</section>; }

function statusLabel(run: AgentRun | undefined, configured: boolean, eventKind?: string) { if (!configured) return { label: "Offline", message: "Concept Generator needs an AI provider to create new concepts.", live: false }; if (!run) return { label: "Idle", message: "Ready to build today’s DINKLY concepts.", live: false }; if (run.status === "Running") { const stages: Record<string, string> = { prepare: "Learning", research: "Researching", build_brief: "Learning", generate_with_you: "Generating", generate_before_after: "Generating", generate_five_story: "Generating", generated: "Generating", validation_retry: "Refining", deduplicate: "Ranking", score: "Ranking", refine: "Refining", select_finalists: "Ranking", save_batch: "Refining", await_review: "Waiting for review" }; const messages: Record<string, string> = { research: "Studying current evidence and verified relationship themes…", deduplicate: "Removing stories that are too similar to previous work…", score: "Ranking candidates for clarity, originality, and execution…", refine: "Refining the strongest scenes…" }; return { label: stages[eventKind ?? ""] ?? "Generating", message: messages[eventKind ?? ""] ?? (run.kind === "concept-generator-replacement" || run.kind === "content-concept-replacement" ? "Refining one replacement concept…" : "Building today’s DINKLY concepts…"), live: true }; } if (run.status === "Failed") return { label: "Failed", message: run.error || "The last assignment could not be completed.", live: false }; if (run.status === "Skipped") return { label: "Needs attention", message: run.error || "The scheduled run was skipped safely.", live: false }; return { label: "Waiting for review", message: "Today’s strongest concepts are ready for you.", live: false }; }
function RunTime({ label, value }: { label: string; value?: string | null }) { return <div><p className="text-[9px] font-bold uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-xs font-semibold">{value ? new Date(value).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "—"}</p></div>; }
function pastel(name: string) { const colors: Record<string, string> = { "warm cream": "#f5e7c5", "powder blue": "#cfe4ef", "soft lavender": "#ddd3ef", "warm sage": "#d7dfca", "warm sand": "#e7d4ba", "blush pink": "#efd2d4", pistachio: "#dce6c7", "pastel peach": "#f1d1bb" }; return colors[name] ?? "#e8dfca"; }
