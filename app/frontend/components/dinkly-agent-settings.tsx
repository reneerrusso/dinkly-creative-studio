"use client";

import Image from "next/image";
import { UploadCloud } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

interface ExpressionAsset { state: ExpressionState; custom: boolean; path: string; fallback_path: string; version: string }
type ExpressionState = "idle" | "learning" | "generating" | "reviewing" | "repairing" | "waiting" | "success" | "error";
const order: ExpressionState[] = ["idle", "learning", "generating", "reviewing", "repairing", "waiting", "success", "error"];

export function DinklyAgentSettings() {
  const [assets, setAssets] = useState<ExpressionAsset[]>([]);
  const [uploading, setUploading] = useState<ExpressionState>();
  const [timeout, setTimeoutValue] = useState<string>("off");
  const [customMinutes, setCustomMinutes] = useState("15");
  const [savingTimeout, setSavingTimeout] = useState(false);
  const load = () => api<ExpressionAsset[]>("/api/dinkly-agent/expressions").then(setAssets);
  useEffect(() => { load().catch(() => setAssets([])); api<{ maximum_task_runtime_seconds: number | null }>("/api/dinkly-agent/settings").then(value => { const seconds = value.maximum_task_runtime_seconds; setTimeoutValue(seconds == null ? "off" : [120, 300, 600].includes(seconds) ? String(seconds) : "custom"); if (seconds && ![120, 300, 600].includes(seconds)) setCustomMinutes(String(Math.max(1, Math.round(seconds / 60)))); }).catch(() => undefined); }, []);

  async function saveTimeout() {
    const seconds = timeout === "off" ? null : timeout === "custom" ? Math.max(1, Number(customMinutes) || 1) * 60 : Number(timeout);
    setSavingTimeout(true);
    try { await api("/api/dinkly-agent/settings", { method: "PUT", body: JSON.stringify({ maximum_task_runtime_seconds: seconds }) }); toast.success("Maximum task runtime saved"); }
    catch (error) { toast.error(error instanceof Error ? error.message : "Could not save task timeout"); }
    finally { setSavingTimeout(false); }
  }

  async function upload(state: ExpressionState, file?: File) {
    if (!file) return;
    const body = new FormData(); body.append("file", file);
    setUploading(state);
    try { await api(`/api/dinkly-agent/expressions/${state}`, { method: "PUT", body }); toast.success(`${label(state)} expression saved`); await load(); }
    catch (error) { toast.error(error instanceof Error ? error.message : "Could not save expression"); }
    finally { setUploading(undefined); }
  }

  return <section className="space-y-8">
    <div className="rounded-2xl border border-line bg-white p-5"><p className="text-xs font-bold uppercase tracking-[0.16em] text-muted">Task safety</p><h2 className="mt-2 font-display text-2xl font-semibold">Maximum task runtime</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-muted">Default is Off. When enabled, DINKLY requests the same safe cancellation flow and then continues to the next queued task.</p><div className="mt-4 flex max-w-xl flex-col gap-3 sm:flex-row"><Select aria-label="Maximum task runtime" value={timeout} onChange={event => setTimeoutValue(event.target.value)}><option value="off">Off</option><option value="120">2 minutes</option><option value="300">5 minutes</option><option value="600">10 minutes</option><option value="custom">Custom</option></Select>{timeout === "custom" && <Input aria-label="Custom runtime in minutes" type="number" min="1" value={customMinutes} onChange={event => setCustomMinutes(event.target.value)} placeholder="Minutes"/>}<Button type="button" disabled={savingTimeout} onClick={() => void saveTimeout()}>Save</Button></div></div>
    <div className="space-y-4">
    <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-muted">DINKLY Agent</p><h2 className="mt-2 font-display text-2xl font-semibold">Agent Expressions</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-muted">Optional official PNG expressions. Missing states gracefully use the canonical Social Intelligence portrait; no substitute artwork is generated.</p></div>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{order.map(state => { const asset = assets.find(item => item.state === state); const source = asset?.path ?? "/agents/social-intelligence.png"; return <div key={state} className="rounded-2xl border border-line bg-white p-3"><div className="relative mx-auto aspect-square max-w-32 overflow-hidden rounded-2xl bg-[#f4efe4]"><Image src={`${source}?v=${asset?.version ?? "canonical"}`} alt={`${label(state)} DINKLY Agent expression`} fill unoptimized className="object-contain" /></div><div className="mt-3 flex items-center justify-between gap-2"><div><p className="text-xs font-semibold">{label(state)}</p><p className="text-[9px] text-muted">{asset?.custom ? "Custom expression" : "Canonical fallback"}</p></div><Button asChild size="sm" variant="outline"><label className="cursor-pointer"><UploadCloud className="size-3.5"/><span className="sr-only">Upload {label(state)} expression</span><input type="file" accept="image/png" className="hidden" disabled={uploading === state} onChange={event => { void upload(state, event.target.files?.[0]); event.currentTarget.value = ""; }} /></label></Button></div></div>; })}</div>
    </div>
  </section>;
}

function label(state: ExpressionState) { return state.charAt(0).toUpperCase() + state.slice(1); }
