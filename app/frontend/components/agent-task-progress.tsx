"use client";

import { AlertTriangle, Check, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { TaskCancelControls } from "@/components/task-cancel-controls";
import type { AgentTask, DinklyAgentActivity, GenerationRun } from "@/lib/types";

const steps = [
  { id: "story", label: "Story brief" },
  { id: "compile", label: "Prompt compiled" },
  { id: "references", label: "References loaded" },
  { id: "generate", label: "Generating" },
  { id: "layout", label: "Applying DINKLY layout" },
  { id: "qa", label: "QA" },
  { id: "human_review", label: "Waiting for approval" },
] as const;

export function AgentTaskProgress({ task, run, events, onRetry, onReview }: {
  task: AgentTask;
  run?: GenerationRun | null;
  events: DinklyAgentActivity[];
  onRetry: () => void;
  onReview: () => void;
}) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (!["queued", "running", "cancellation_requested"].includes(task.status)) return; const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, [task.status]);
  const progress = useMemo(() => events.filter(event => event.details?.stage), [events]);
  const latestByStage = new Map<string, DinklyAgentActivity>();
  for (const event of progress) latestByStage.set(String(event.details.stage), event);
  const latest = events.at(-1);
  const generation = latestByStage.get("generate");
  const candidateTotal = Number(generation?.details.total ?? run?.candidate_count ?? 4);
  const candidateCompleted = Math.max(Number(generation?.details.completed ?? 0), run?.candidates.filter(item => item.image_path).length ?? 0);
  const activeCandidate = String(generation?.details.candidate ?? "");
  const modelName = String(generation?.details.model && typeof generation.details.model === "object" ? (generation.details.model as Record<string, unknown>).display_name ?? "" : run?.selected_model_info?.display_name ?? "");
  const stage = currentStage(task, latest);
  const started = task.started_at ?? task.created_at;
  const finished = task.completed_at ?? run?.completed_at ?? null;

  if (task.status === "failed") return <section aria-label="Task failed" className="rounded-[24px] border border-red-200 bg-red-50 p-5"><div className="flex items-center gap-2 text-red-800"><AlertTriangle className="size-4"/><p className="text-xs font-black uppercase tracking-[.15em]">DINKLY Agent · Needs Attention</p></div><h2 className="mt-3 text-lg font-semibold">Generation failed at: {activeCandidate ? `Candidate ${activeCandidate}` : stage}</h2><p className="mt-2 text-sm leading-6 text-red-900">Reason: {task.error || "The backend did not record a reason."}</p><div className="mt-4 flex gap-2"><Button type="button" onClick={onRetry}><RotateCcw className="size-4"/>Retry</Button><Button type="button" variant="outline" onClick={() => document.getElementById("agent-task-details")?.scrollIntoView({ behavior: "smooth" })}>View Details</Button></div></section>;
  if (task.status === "cancelled") return <section aria-label="Task cancelled" className="rounded-[24px] border border-black/[.08] bg-white p-5"><p className="text-xs font-black uppercase tracking-[.15em] text-muted">DINKLY Agent · Cancelled</p><h2 className="mt-3 text-lg font-semibold">This task stopped safely.</h2><p className="mt-2 text-sm text-muted">No further generation work is running.</p><Button type="button" className="mt-4" variant="outline" onClick={onRetry}><RotateCcw className="size-4"/>Restart Task</Button></section>;

  return <section aria-label="Active task progress" className="overflow-hidden rounded-[24px] border border-black/[.08] bg-white shadow-sm">
    <div className="flex flex-col justify-between gap-4 border-b border-line p-5 sm:flex-row sm:items-center"><div><div className="flex items-center gap-2"><p className="text-[10px] font-black uppercase tracking-[.17em] text-[#8c6325]">DINKLY Agent · {taskLabel(task.status, stage)}</p>{task.status === "running" && <WorkingDots/>}</div><h2 className="mt-2 text-lg font-semibold">{run ? run.concept_text : task.user_instruction}</h2><p aria-live="polite" className="mt-1 text-sm text-muted">{headline(stage, activeCandidate, candidateCompleted, candidateTotal, modelName)}</p></div><div className="flex gap-2">{task.status === "waiting_for_human" && <Button type="button" onClick={onReview}>Review Comic</Button>}<TaskCancelControls task={task} allowSkip onUpdated={() => window.dispatchEvent(new Event("dinkly-task-updated"))}/></div></div>
    <div className="grid gap-5 p-5 lg:grid-cols-[1.1fr_.9fr]"><ol className="space-y-2">{steps.map(step => { const event = latestByStage.get(step.id); const status = stepStatus(step.id, task, event, run); const label = step.id === "generate" && candidateTotal ? `${step.label} ${candidateCompleted} / ${candidateTotal}` : step.label; return <li key={step.id} aria-label={`${label}: ${status}`} className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm ${status === "active" ? "bg-[#fbf4dc] font-semibold" : ""}`}>{status === "complete" ? <span aria-hidden="true" className="flex size-4 shrink-0 items-center justify-center rounded-full bg-emerald-700 text-white"><Check className="size-2.5" strokeWidth={3}/></span> : status === "active" ? <WorkingDots/> : <Circle className="size-3 text-neutral-300"/>}<span>{label}</span></li>; })}</ol><dl id="agent-task-details" className="grid content-start gap-3 rounded-2xl bg-wash p-4 text-xs"><Fact label="Current task" value={task.user_instruction}/><Fact label="Started" value={new Date(started).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}/><Fact label="Elapsed" value={elapsed(started, finished, now)}/><Fact label="Current" value={headline(stage, activeCandidate, candidateCompleted, candidateTotal, modelName)}/><Fact label="Latest event" value={latest?.message ?? (task.status === "queued" ? "Assignment saved in the Agent queue." : task.status === "waiting_for_human" ? "Ready for approval." : "Waiting for the next persisted event.")}/></dl></div>
  </section>;
}

function currentStage(task: AgentTask, latest?: DinklyAgentActivity) { if (task.status === "cancellation_requested") return "stopping"; if (task.status === "queued") return "queued"; if (task.status === "waiting_for_human") return "human_review"; if (task.status === "completed") return "completed"; return String(latest?.details?.stage ?? (task.task_type === "repair_comic" ? "repair" : "preparing")); }
function taskLabel(status: AgentTask["status"], stage: string) { if (status === "cancellation_requested") return "STOPPING"; if (status === "queued") return "Queued"; if (status === "waiting_for_human") return "Waiting For You"; if (status === "completed") return "Completed"; return ({ story: "Preparing", compile: "Preparing", references: "Preparing", generate: "Generating", layout: "Applying Layout", qa: "Reviewing", repair: "Repairing", learning: "Learning" } as Record<string, string>)[stage] ?? "Working"; }
function headline(stage: string, candidate: string, completed: number, total: number, model: string) { if (stage === "stopping") return "Finishing the current safe step…"; if (stage === "queued") return "Queued for the DINKLY Agent worker."; if (stage === "human_review") return "The strongest candidate is ready for approval."; if (stage === "generate") return candidate ? `Creating Candidate ${candidate} of ${total}${model ? ` with ${model}` : ""}` : `Generating ${completed} / ${total} candidates${model ? ` with ${model}` : ""}`; if (stage === "layout") return "Applying the final DINKLY 80/20 layout."; if (stage === "qa") return "Reviewing character consistency, scene accuracy, and prompt alignment."; if (stage === "repair") return "Repairing the selected candidate."; if (stage === "completed") return "Task completed."; return "Preparing the story, prompt, and locked references."; }
function stepStatus(id: string, task: AgentTask, event?: DinklyAgentActivity, run?: GenerationRun | null): "pending" | "active" | "complete" {
  if (id === "human_review") return task.status === "waiting_for_human" ? "active" : ["approved", "rejected"].includes(run?.status ?? "") ? "complete" : "pending";
  if (task.status === "waiting_for_human" || ["awaiting_human", "approved", "rejected"].includes(run?.status ?? "")) return "complete";
  const raw = String(event?.details?.status ?? "");
  if (raw === "complete" || raw === "skipped") return "complete";
  if (raw === "active" || raw === "warning") return "active";
  if (task.status === "completed") return "complete";

  // Persisted run state is the authoritative fallback when earlier task events
  // have been compacted or were recorded before this task was linked to the run.
  const completedThrough = ({
    draft: -1,
    compiling: 0,
    generating: 2,
    reviewing: 4,
    repairing: 5,
    awaiting_human: 5,
    approved: 5,
    rejected: 5,
    failed: -1,
    cancelled: -1,
  } as Record<string, number>)[run?.status ?? ""] ?? -1;
  const index = steps.findIndex(step => step.id === id);
  if (index <= completedThrough) return "complete";
  if (run?.status === "compiling" && id === "compile") return "active";
  if (run?.status === "generating" && id === "generate") return "active";
  if (run?.status === "reviewing" && id === "qa") return "active";
  if (run?.status === "repairing" && id === "qa") return "active";
  return "pending";
}
function Fact({ label, value }: { label: string; value: string }) { return <div><dt className="text-[9px] font-bold uppercase tracking-[.13em] text-muted">{label}</dt><dd className="mt-1 leading-5">{value}</dd></div>; }
function WorkingDots() { return <span aria-label="Working" className="inline-flex shrink-0 gap-0.5 text-[#a47b1b]"><i className="size-1.5 animate-pulse rounded-full bg-current"/><i className="size-1.5 animate-pulse rounded-full bg-current [animation-delay:180ms]"/><i className="size-1.5 animate-pulse rounded-full bg-current [animation-delay:360ms]"/></span>; }
function Circle({ className }: { className?: string }) { return <span aria-hidden="true" className={`${className ?? ""} rounded-full border border-current`}/>; }
function elapsed(start: string, end: string | null, now: number) { const seconds = Math.max(0, Math.floor(((end ? new Date(end).getTime() : now) - new Date(start).getTime()) / 1000)); return seconds < 60 ? `${seconds} sec` : `${Math.floor(seconds / 60)} min ${seconds % 60} sec`; }
