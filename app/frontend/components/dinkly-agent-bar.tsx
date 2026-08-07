"use client";

import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { DinklyAgentAvatar } from "@/components/dinkly-agent-avatar";
import { TaskCancelControls } from "@/components/task-cancel-controls";
import { Button } from "@/components/ui/button";
import { API_URL, api } from "@/lib/api";
import type { AgentTask, AgentWorkspace, DinklyAgentActivity, DinklyAgentRuntimeState } from "@/lib/types";
import { cn } from "@/lib/utils";

type BarKind = "working" | "idle" | "error";

export function DinklyAgentBar() {
  const [workspace, setWorkspace] = useState<AgentWorkspace>();
  const [events, setEvents] = useState<DinklyAgentActivity[]>([]);
  const [open, setOpen] = useState(false);
  const [unreachable, setUnreachable] = useState(false);

  const load = useCallback(async () => {
    try {
      const [desk, activity] = await Promise.all([
        api<AgentWorkspace>("/api/dinkly-agent/workspace"),
        api<DinklyAgentActivity[]>("/api/dinkly-agent/events?limit=60"),
      ]);
      setWorkspace(desk); setEvents(activity); setUnreachable(false);
    } catch { setUnreachable(true); }
  }, []);

  useEffect(() => {
    void load();
    const poll = window.setInterval(() => void load(), 5000);
    if (typeof EventSource === "undefined") return () => window.clearInterval(poll);
    const source = new EventSource(`${API_URL}/api/dinkly-agent/stream`);
    const refresh = (raw: Event) => {
      try {
        const event = JSON.parse((raw as MessageEvent).data) as DinklyAgentActivity;
        setEvents(current => current.some(item => item.id === event.id) ? current : [...current.slice(-59), event]);
      } catch { /* The persisted poll restores canonical state. */ }
      void load();
    };
    source.addEventListener("activity", refresh);
    return () => { window.clearInterval(poll); source.removeEventListener("activity", refresh); source.close(); };
  }, [load]);

  const task = workspace?.current_task ?? null;
  const relevant = useMemo(() => task ? events.filter(event => event.source_run_id === task.id || event.details?.task_id === task.id || task.run_ids.includes(String(event.source_run_id))) : events, [events, task]);
  const latest = relevant.at(-1) ?? events.at(-1);
  const presentation = describeAgent(workspace?.agent, task, latest, unreachable);
  const waiting = workspace ? Object.values(workspace.waiting).reduce((sum, count) => sum + count, 0) : 0;
  const detailHref = task?.status === "waiting_for_human" || waiting > 0 ? "/approvals" : "/agent";

  return <div className="sticky top-16 z-20 border-b border-black/[0.055] bg-[#f3ecdc]/95 px-4 backdrop-blur sm:px-6 lg:px-8">
    <div className="relative mx-auto flex h-[60px] w-full max-w-[1500px] items-center">
      <button type="button" aria-expanded={open} aria-label="Open DINKLY Agent status" onClick={() => setOpen(value => !value)} className="flex min-w-0 max-w-full items-center gap-3 rounded-xl px-1 py-1.5 text-left hover:bg-white/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b58b24]">
        <DinklyAgentAvatar source={workspace?.agent.expression.path}/>
        <span className="min-w-0"><span className="flex items-center gap-2"><span aria-hidden="true" className={cn("size-2 shrink-0 rounded-full", presentation.kind === "working" ? "bg-emerald-600" : presentation.kind === "error" ? "bg-red-600" : "bg-[#d2a62c]")}/><span className="truncate text-[11px] font-black uppercase tracking-[.14em] text-[#2e2a24]">DINKLY <span className="hidden sm:inline">Agent</span></span><span className="text-[9px] font-black uppercase tracking-[.13em] text-[#71695f]">{presentation.label}</span></span><span className="mt-0.5 block max-w-[calc(100vw-110px)] truncate text-xs text-[#655e54] sm:max-w-[560px]">{presentation.activity}</span></span>
      </button>
      {open && <section aria-label="DINKLY Agent status details" className="absolute left-0 top-[calc(100%+.55rem)] w-[min(92vw,390px)] rounded-2xl border border-line bg-[#fbfaf6] p-4 shadow-2xl">
        <div className="flex items-center gap-3"><DinklyAgentAvatar source={workspace?.agent.expression.path}/><div className="min-w-0"><p className="text-sm font-semibold">DINKLY Agent</p><p className="mt-0.5 text-xs text-muted">{presentation.activity}</p></div></div>
        {task ? <dl className="mt-4 grid gap-3 rounded-xl bg-white p-4 text-xs"><Fact label="Current task" value={task.user_instruction}/><Fact label="Current step" value={presentation.step}/><Fact label="Started" value={formatTime(task.started_at ?? task.created_at)}/><Fact label="Latest event" value={latest?.message ?? workspace?.agent.last_event ?? "No event recorded yet."}/></dl> : <div className="mt-4 rounded-xl bg-white p-4"><p className="text-[9px] font-black uppercase tracking-[.15em] text-muted">Recent activity</p><p className="mt-2 text-xs leading-5">{workspace?.recent_work[0]?.message ?? latest?.message ?? "No recent work yet."}</p></div>}
        <div className="mt-4 flex flex-wrap gap-2"><Button asChild size="sm"><Link href="/agent" onClick={() => setOpen(false)}>Open Agent <ArrowRight className="size-3.5"/></Link></Button><Button asChild size="sm" variant="outline"><Link href={detailHref} onClick={() => setOpen(false)}>{task ? "View Live Work" : waiting ? "View approvals" : "Start a task"}<ArrowUpRight className="size-3.5"/></Link></Button>{task && <TaskCancelControls task={task} onUpdated={() => void load()}/>}</div>
      </section>}
    </div>
  </div>;
}

function describeAgent(runtime?: DinklyAgentRuntimeState, task?: AgentTask | null, event?: DinklyAgentActivity, unreachable = false): { kind: BarKind; label: string; activity: string; step: string } {
  if (unreachable) return { kind: "error", label: "Needs attention", activity: "Agent backend unavailable", step: "Connection error" };
  if (task?.status === "failed" || runtime?.state === "error") return { kind: "error", label: "Needs attention", activity: task?.error || runtime?.message || "The current task failed", step: "Failed" };
  if (task?.status === "cancellation_requested") return { kind: "working", label: "STOPPING", activity: "Finishing the current safe step…", step: "Safe cancellation" };
  const stage = String(event?.details?.stage ?? "");
  const candidate = String(event?.details?.candidate ?? "");
  const completed = Number(event?.details?.completed ?? 0);
  const total = Number(event?.details?.total ?? 0);
  if (task?.status === "waiting_for_human" || runtime?.state === "waiting_for_human") return { kind: "idle", label: "Waiting", activity: "Waiting for your approval", step: "Human approval" };
  if (task && ["queued", "running"].includes(task.status)) {
    if (stage === "generate") return { kind: "working", label: "Working", activity: candidate ? `Generating Candidate ${candidate}${total ? ` · ${completed} of ${total}` : ""}` : `Generating ${completed} of ${total} candidates`, step: "Generation" };
    if (stage === "qa") return { kind: "working", label: "Working", activity: candidate ? `Running QA on Candidate ${candidate}` : "Running artwork QA", step: "QA" };
    if (stage === "layout") return { kind: "working", label: "Working", activity: "Applying DINKLY 80/20 layout", step: "Final layout" };
    if (stage === "repair") return { kind: "working", label: "Working", activity: candidate ? `Repairing Candidate ${candidate}` : "Repairing selected artwork", step: "Repair" };
    if (task.task_type === "learn" || stage === "learning") return { kind: "working", label: "Working", activity: runtime?.message || "Learning from approved work", step: "Learning" };
    return { kind: "working", label: "Working", activity: task.status === "queued" ? `Queued: ${task.user_instruction}` : runtime?.message || task.user_instruction, step: stage ? titleCase(stage) : "Preparing" };
  }
  if (runtime?.state === "success") return { kind: "idle", label: "Completed", activity: runtime.message || "Completed", step: "Completed" };
  return { kind: "idle", label: "Idle", activity: "Ready when you are", step: "Idle" };
}

function Fact({ label, value }: { label: string; value: string }) { return <div><dt className="text-[9px] font-black uppercase tracking-[.13em] text-muted">{label}</dt><dd className="mt-1 leading-5 text-[#403b34]">{value}</dd></div>; }
function formatTime(value: string) { return new Date(value).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); }
function titleCase(value: string) { return value ? value.charAt(0).toUpperCase() + value.slice(1).replaceAll("_", " ") : "Preparing"; }
