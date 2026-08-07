"use client";

import Link from "next/link";
import { AlertCircle, ArrowLeft, ArrowUpRight, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { AgentTaskProgress } from "@/components/agent-task-progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { API_URL, ApiError, api } from "@/lib/api";
import type { AgentTask, DinklyAgentActivity, GenerationRun } from "@/lib/types";

export default function AgentTaskPage() {
  const { taskId } = useParams<{ taskId: string }>(); const router = useRouter();
  const [task, setTask] = useState<AgentTask>(); const [run, setRun] = useState<GenerationRun | null>(null); const [events, setEvents] = useState<DinklyAgentActivity[]>([]); const [missing, setMissing] = useState(false); const [loadError, setLoadError] = useState<string>();
  const load = useCallback(async () => { try { const record = await api<AgentTask>(`/api/dinkly-agent/tasks/${taskId}`); setTask(record); setEvents(await api<DinklyAgentActivity[]>(`/api/dinkly-agent/tasks/${taskId}/events`).catch(() => [])); setRun(record.run_ids[0] ? await api<GenerationRun>(`/api/generation-engine/runs/${record.run_ids[0]}`).catch(() => null) : null); setMissing(false); setLoadError(undefined); } catch (error) { setMissing(error instanceof ApiError && error.status === 404); setLoadError(error instanceof Error ? error.message : "The live task is unavailable."); } }, [taskId]);
  useEffect(() => { let disposed = false; let poll: number | undefined; const refresh = async () => { await load(); if (!disposed) poll = window.setTimeout(() => void refresh(), 2200); }; void refresh(); return () => { disposed = true; if (poll) window.clearTimeout(poll); }; }, [load]);
  useEffect(() => { if (!task || !["queued", "running", "cancellation_requested"].includes(task.status) || typeof EventSource === "undefined") return; const source = new EventSource(`${API_URL}/api/dinkly-agent/tasks/${task.id}/stream`); const update = () => void load(); source.addEventListener("activity", update); return () => { source.removeEventListener("activity", update); source.close(); }; }, [load, task]);
  async function retry() { if (!task) return; try { const response = await api<{ task: AgentTask }>(`/api/dinkly-agent/tasks/${task.id}/restart`, { method: "POST" }); router.push(`/agent/tasks/${response.task.id}`); } catch (error) { toast.error(error instanceof Error ? error.message : "Could not retry task"); } }
  if (missing) return <div className="mx-auto max-w-4xl py-20 text-center"><h1 className="text-2xl font-semibold">Task not found</h1><Button asChild className="mt-5"><Link href="/agent">Back to DINKLY Agent</Link></Button></div>;
  if (!task && loadError) return <div className="mx-auto max-w-4xl py-20 text-center"><AlertCircle className="mx-auto size-7 text-[#a14b3f]"/><h1 className="mt-4 text-2xl font-semibold">Live task unavailable</h1><p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted">{loadError}</p><Button className="mt-5" onClick={() => void load()}><RefreshCw className="size-4"/>Retry</Button></div>;
  if (!task) return <div className="mx-auto max-w-4xl py-20 text-center text-sm text-muted">Opening live task…</div>;
  const comicUrl = task.run_ids[0] ? `/comics/${task.run_ids[0]}` : "/approvals";
  return <div className="mx-auto max-w-6xl space-y-6 pb-16"><Button asChild variant="ghost"><Link href="/agent"><ArrowLeft className="size-4"/>DINKLY Agent</Link></Button><header><div className="flex flex-wrap gap-2"><Badge>Live task</Badge><Badge>{task.source_channel === "slack" ? "From Slack" : `From ${task.source_channel}`}</Badge></div><h1 className="mt-3 text-3xl font-semibold tracking-[-.04em]">{run?.concept_text || task.user_instruction}</h1><p className="mt-2 text-xs text-muted">Task {task.id} · updates automatically</p></header><AgentTaskProgress task={task} run={run} events={events} onRetry={() => void retry()} onReview={() => router.push(comicUrl)}/>{task.run_ids[0] && <div className="flex justify-end"><Button asChild variant="outline"><Link href={comicUrl}>Open comic details <ArrowUpRight className="size-3.5"/></Link></Button></div>}</div>;
}
