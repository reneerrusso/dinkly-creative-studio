"use client";

import Link from "next/link";
import { ArrowRight, ArrowUp, BookHeart, CheckCircle2, Clock3, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { AgentTaskProgress } from "@/components/agent-task-progress";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { API_URL, api } from "@/lib/api";
import type { AgentConversationMessage, AgentTask, AgentWorkspace, DinklyAgentActivity, GenerationRun } from "@/lib/types";
import type { StorySeed } from "@/lib/story-seed";

const threadId = "web-default";
const suggestions = ["Generate 10 concepts", "Make the coffee comic", "What have you learned?", "Show me what needs approval"];

export default function AgentPage() {
  const [workspace, setWorkspace] = useState<AgentWorkspace>();
  const [messages, setMessages] = useState<AgentConversationMessage[]>([]);
  const [stories, setStories] = useState<StorySeed[]>([]);
  const [storyId, setStoryId] = useState("");
  const [storyLoading, setStoryLoading] = useState(true);
  const [storyError, setStoryError] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [activeTask, setActiveTask] = useState<AgentTask>();
  const [activeRun, setActiveRun] = useState<GenerationRun | null>(null);
  const [taskEvents, setTaskEvents] = useState<DinklyAgentActivity[]>([]);

  const load = useCallback(async () => {
    const [desk, conversation] = await Promise.all([
      api<AgentWorkspace>("/api/dinkly-agent/workspace"),
      api<AgentConversationMessage[]>(`/api/dinkly-agent/conversations?channel=web&thread_id=${threadId}&limit=80`),
    ]);
    setWorkspace(desk); setMessages(conversation);
    setActiveTask(desk.current_task ?? undefined); setActiveRun(desk.current_run ?? null);
    if (!desk.current_task) setTaskEvents([]);
  }, []);

  const refreshTask = useCallback(async (taskId: string) => {
    const task = await api<AgentTask>(`/api/dinkly-agent/tasks/${taskId}`);
    setActiveTask(task);
    setTaskEvents(await api<DinklyAgentActivity[]>(`/api/dinkly-agent/tasks/${taskId}/events`).catch(() => []));
    if (task.run_ids?.[0]) setActiveRun(await api<GenerationRun>(`/api/generation-engine/runs/${task.run_ids[0]}`).catch(() => null));
  }, []);

  const loadStories = useCallback(async () => {
    setStoryLoading(true); setStoryError("");
    try { const records = await api<StorySeed[]>("/api/story-library", { timeoutMs: 10_000 }); setStories(records); if (!records.length) setStoryError("The Story Library is empty."); }
    catch (error) { setStories([]); setStoryError(error instanceof Error ? error.message : "The Story Library could not be loaded."); }
    finally { setStoryLoading(false); }
  }, []);

  useEffect(() => { void load(); void loadStories(); const poll = window.setInterval(() => { void load(); if (activeTask?.id) void refreshTask(activeTask.id); }, 2200); return () => window.clearInterval(poll); }, [activeTask?.id, load, loadStories, refreshTask]);
  useEffect(() => {
    if (!activeTask?.id || !["queued", "running", "cancellation_requested"].includes(activeTask.status) || typeof EventSource === "undefined") return;
    const source = new EventSource(`${API_URL}/api/dinkly-agent/tasks/${activeTask.id}/stream`);
    const update = () => { void refreshTask(activeTask.id); void load(); };
    source.addEventListener("activity", update);
    return () => { source.removeEventListener("activity", update); source.close(); };
  }, [activeTask?.id, activeTask?.status, load, refreshTask]);
  useEffect(() => { const refresh = () => void load(); window.addEventListener("dinkly-task-updated", refresh); return () => window.removeEventListener("dinkly-task-updated", refresh); }, [load]);

  async function assign(value = message, context: Record<string, unknown> = {}) {
    const clean = value.trim(); if (!clean) return;
    setSending(true);
    try {
      const result = await api<{ task: AgentTask }>("/api/dinkly-agent/instructions", { method: "POST", body: JSON.stringify({ message: clean, thread_id: threadId, user_id: "owner", context }) });
      setActiveTask(result.task); setActiveRun(null); setTaskEvents([]); setMessage(""); setStoryId(""); await load();
    } catch (error) { toast.error(error instanceof Error ? error.message : "DINKLY could not accept that assignment"); }
    finally { setSending(false); }
  }

  function buildSelectedStory() {
    const story = stories.find(item => item.id === storyId);
    if (!story) { toast.error("Choose a Story Library concept first"); return; }
    const left = story.title_left ?? story.title; const right = story.title_right ?? `${left} WITH YOU`;
    void assign(`Generate ${left} / ${right}.`, { story_id: story.id });
  }

  const activeWork = activeTask && ["queued", "running", "cancellation_requested"].includes(activeTask.status) ? activeTask : undefined;
  const waitingTotal = workspace ? Object.values(workspace.waiting).reduce((sum, value) => sum + value, 0) : 0;

  return <div className="mx-auto max-w-6xl space-y-8 pb-16">
    <header><p className="text-[10px] font-bold uppercase tracking-[.2em] text-[#8c6325]">Employee workspace</p><h1 className="mt-2 text-3xl font-semibold tracking-[-.035em]">DINKLY Agent</h1><p className="mt-2 text-sm text-muted">Tell DINKLY what to work on.</p></header>

    <section aria-labelledby="agent-chat-title"><h2 id="agent-chat-title" className="mb-3 text-[10px] font-black uppercase tracking-[.18em] text-muted">Chat</h2><Card><CardContent className="space-y-4 p-5 sm:p-7">
      <div className="rounded-2xl border border-black/[0.08] bg-white p-3 shadow-sm"><Textarea aria-label="DINKLY assignment" value={message} onChange={event => setMessage(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void assign(); } }} placeholder="What do you want DINKLY to work on?" className="min-h-28 resize-none border-0 bg-transparent text-base shadow-none focus-visible:ring-0"/><div className="flex items-center justify-between gap-3 border-t border-line pt-3"><p className="text-[10px] text-muted">Enter to assign · Shift + Enter for a new line</p><Button aria-label="Send assignment" size="icon" onClick={() => void assign()} disabled={sending || !message.trim()} className="rounded-full"><ArrowUp className="size-4"/></Button></div></div>
      <div className="flex flex-wrap gap-2">{suggestions.map(value => <button key={value} type="button" onClick={() => setMessage(value)} className="rounded-full border border-line bg-white px-3 py-2 text-[11px] font-semibold text-muted hover:bg-wash">{value}</button>)}</div>
      {messages.length > 0 && <div className="max-h-[320px] space-y-3 overflow-y-auto border-t border-line pt-4" aria-label="Recent conversation" aria-live="polite">{messages.map(item => <div key={item.id} className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}><div className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-6 ${item.role === "user" ? "bg-ink text-white" : "bg-wash text-ink"}`}><p>{item.message}</p><p className={`mt-1 text-[9px] ${item.role === "user" ? "text-white/60" : "text-muted"}`}>{new Date(item.created_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</p></div></div>)}</div>}
      <div className="grid gap-4 border-t border-line pt-4 sm:grid-cols-[1fr_auto] sm:items-end"><div><div className="flex items-center gap-2"><BookHeart className="size-4 text-[#9b7521]"/><p className="text-xs font-bold uppercase tracking-[.14em]">Start from the Story Library</p></div><Select aria-label="Choose from Story Library" className="mt-3" value={storyId} onChange={event => setStoryId(event.target.value)} disabled={storyLoading}><option value="">{storyLoading ? "Loading stories…" : "Choose a story…"}</option>{stories.map(story => <option key={story.id} value={story.id}>{story.title_left ?? story.title} / {story.title_right ?? "WITH YOU"}</option>)}</Select>{storyError && <div className="mt-2 flex items-center gap-3"><p className="text-xs text-red-700">{storyError}</p><Button type="button" variant="outline" size="sm" onClick={() => void loadStories()}>Retry Story Library</Button></div>}</div><Button onClick={buildSelectedStory} disabled={!storyId || sending || storyLoading}><Sparkles className="size-4"/>{sending ? "Assigning…" : "Build Story"}</Button></div>
    </CardContent></Card></section>

    {activeWork && <section aria-labelledby="current-work-title"><h2 id="current-work-title" className="mb-3 text-[10px] font-black uppercase tracking-[.18em] text-muted">Current Work</h2><AgentTaskProgress task={activeWork} run={activeRun} events={taskEvents} onRetry={() => void assign(activeWork.user_instruction, activeWork.context)} onReview={() => window.location.assign("/approvals")}/></section>}

    {waitingTotal > 0 && <section aria-labelledby="waiting-title"><h2 id="waiting-title" className="mb-3 text-[10px] font-black uppercase tracking-[.18em] text-muted">Waiting for You</h2><Link href="/approvals"><Card className="transition hover:border-[#b58b24]"><CardContent className="flex items-center justify-between gap-5 p-5"><div className="flex items-center gap-4"><span className="flex size-10 items-center justify-center rounded-full bg-[#f2df9d]"><CheckCircle2 className="size-4"/></span><div><p className="text-sm font-semibold">{waitingTotal} decision{waitingTotal === 1 ? "" : "s"} waiting</p><p className="mt-1 text-xs text-muted">{workspace?.waiting.comics ?? 0} comics · {workspace?.waiting.concepts ?? 0} concepts · {workspace?.waiting.brain_updates ?? 0} Brain updates</p></div></div><ArrowRight className="size-4 text-muted"/></CardContent></Card></Link></section>}

    <section aria-labelledby="recent-work-title"><div className="mb-3 flex items-center justify-between"><h2 id="recent-work-title" className="text-[10px] font-black uppercase tracking-[.18em] text-muted">Recent Work</h2><Button asChild variant="ghost" size="sm"><Link href="/history">Full activity <ArrowRight className="size-3.5"/></Link></Button></div>{workspace?.recent_work.length ? <div className="overflow-hidden rounded-2xl border border-line bg-white">{workspace.recent_work.slice(0, 6).map((entry, index) => <div key={entry.id} className={`flex items-start gap-3 p-4 ${index ? "border-t border-line" : ""}`}><Clock3 className="mt-0.5 size-4 shrink-0 text-[#9b7521]"/><div className="min-w-0"><p className="text-sm font-semibold leading-5">{entry.message}</p><p className="mt-1 text-[10px] capitalize text-muted">{new Date(entry.timestamp).toLocaleString()} · {entry.source_channel}</p></div></div>)}</div> : <Card><CardContent className="py-10 text-center"><p className="text-sm font-semibold">No completed work yet</p><p className="mt-1 text-xs text-muted">Finished assignments will appear here.</p></CardContent></Card>}</section>
  </div>;
}
