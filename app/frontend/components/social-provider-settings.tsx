"use client";

import { AlertTriangle, CheckCircle2, EyeOff, Pause, Play, RefreshCw, Save, ShieldCheck, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { api, getSocialDataProviders } from "@/lib/api";
import type { ProviderBudgetSettings, ProviderUsageSummary, SocialProviderStatus } from "@/lib/types";

interface BudgetResponse {
  settings: ProviderBudgetSettings;
  usage: ProviderUsageSummary;
  provider: { status: string; paused: boolean; circuit_state: string; message: string };
}

export function SocialProviderSettings({ compact = false, onChange }: { compact?: boolean; onChange?: () => void }) {
  const [provider, setProvider] = useState<SocialProviderStatus>();
  const [budget, setBudget] = useState<ProviderBudgetSettings>();
  const [usage, setUsage] = useState<ProviderUsageSummary>();
  const [token, setToken] = useState("");
  const [instagramActor, setInstagramActor] = useState("");
  const [tiktokActor, setTiktokActor] = useState("");
  const [instagramEnabled, setInstagramEnabled] = useState(true);
  const [tiktokEnabled, setTiktokEnabled] = useState(true);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [health, setHealth] = useState<Record<string, { status: string; ready?: boolean; message?: string }> | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [confirmResume, setConfirmResume] = useState(false);

  const load = useCallback(async () => {
    const [providers, budgetData] = await Promise.all([
      getSocialDataProviders(),
      api<BudgetResponse>("/api/provider-budget"),
    ]);
    const apify = providers.find(item => item.name === "Apify") ?? providers[0];
    setProvider(apify);
    setBudget(budgetData.settings);
    setUsage(budgetData.usage);
    setInstagramActor(apify?.instagram_actor_id ?? "");
    setTiktokActor(apify?.tiktok_actor_id ?? "");
    setInstagramEnabled(apify?.platforms?.instagram?.enabled ?? true);
    setTiktokEnabled(apify?.platforms?.tiktok?.enabled ?? true);
  }, []);

  useEffect(() => { load().catch(() => undefined); }, [load]);

  async function saveProvider() {
    if (!provider?.configured && !token.trim()) {
      toast.error("Enter an Apify API token first");
      return;
    }
    setBusy(true);
    try {
      if (token.trim()) {
        await api("/api/social-data-providers/apify/configure", {
          method: "POST",
          body: JSON.stringify({ token, instagram_actor_id: instagramActor, tiktok_actor_id: tiktokActor, instagram_enabled: instagramEnabled, tiktok_enabled: tiktokEnabled }),
        });
        setToken("");
        toast.success("Apify key saved securely and hidden");
      } else {
        await api("/api/social-data-providers/apify/actors", {
          method: "PUT",
          body: JSON.stringify({ instagram_actor_id: instagramActor, tiktok_actor_id: tiktokActor, instagram_enabled: instagramEnabled, tiktok_enabled: tiktokEnabled }),
        });
        toast.success("Platform settings updated");
      }
      await load();
      onChange?.();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Provider settings could not be saved");
    } finally {
      setBusy(false);
    }
  }

  async function testConnection() {
    setBusy(true);
    try {
      const result = await api<{ connected?: boolean; message: string; token?: { status: string }; platforms?: Record<string, { status: string; ready?: boolean; message?: string }> }>("/api/social-data-providers/test", { method: "POST", body: JSON.stringify({ provider: "apify" }) });
      setHealth({ ...(result.platforms ?? {}), apify: { status: result.token?.status ?? "Unavailable" } });
      result.connected ? toast.success("Connection test complete") : toast.error(result.message);
      await load();
      onChange?.();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Connection test failed");
    } finally {
      setBusy(false);
    }
  }

  async function removeKey() {
    setBusy(true);
    try {
      await api("/api/social-data-providers/apify/configure", { method: "DELETE" });
      setToken("");
      setConfirmRemove(false);
      await load();
      onChange?.();
      toast.success("Local Apify key removed");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Key removal failed");
    } finally {
      setBusy(false);
    }
  }

  async function pauseOrResume() {
    const resume = provider?.paused;
    if (resume && !confirmResume) {
      setConfirmResume(true);
      return;
    }
    setBusy(true);
    try {
      await api(`/api/social-data-providers/apify/${resume ? "resume" : "pause"}`, {
        method: "POST",
        body: resume ? JSON.stringify({ confirmed: true }) : "{}",
      });
      setConfirmResume(false);
      await load();
      onChange?.();
      toast.success(resume ? "Provider resumed; test it before refreshing" : "Provider paused");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Provider state could not be changed");
    } finally {
      setBusy(false);
    }
  }

  async function saveBudget() {
    if (!budget) return;
    setBusy(true);
    try {
      await api("/api/provider-budget", { method: "PUT", body: JSON.stringify(budget) });
      await load();
      onChange?.();
      toast.success("Budget guardrails saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Budget settings could not be saved");
    } finally {
      setBusy(false);
    }
  }

  return <div id="social-data-providers" className="space-y-5">
    <Card className="border-black/[0.055] shadow-none">
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div><CardTitle>Apify</CardTitle><p className="mt-1 text-sm leading-6 text-muted">Optional public Instagram and TikTok retrieval with recommended providers selected for you.</p></div>
        <ProviderState state={provider?.state ?? "Checking"}/>
      </CardHeader>
      <CardContent className="space-y-5">
        {!provider?.configured ? <div className="rounded-2xl bg-[#f6eed7] p-4 text-sm leading-6"><strong>Add Apify API key</strong><p className="mt-1 text-muted">The token is sent only to the local backend, stored in a restricted ignored file, and never returned to this page.</p></div> : <div className="flex items-center justify-between rounded-2xl bg-[#e5eee4] p-4 text-sm"><div className="flex items-center gap-2"><ShieldCheck className="size-4 text-emerald-700"/><span>{provider.masked_token || "Configured"}</span></div><span className="text-xs text-muted">Token hidden</span></div>}
        <Field label={provider?.configured ? "Replace Apify API token" : "Apify API token"} htmlFor="apify-token"><Input id="apify-token" type="password" autoComplete="off" value={token} onChange={event => setToken(event.target.value)} placeholder={provider?.configured ? "Leave blank to keep current key" : "Paste token"}/></Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <PlatformCard name="Instagram" enabled={instagramEnabled} onChange={setInstagramEnabled} status={provider?.platforms?.instagram} health={health?.instagram} onAdvanced={() => setAdvancedOpen(true)}/>
          <PlatformCard name="TikTok" enabled={tiktokEnabled} onChange={setTiktokEnabled} status={provider?.platforms?.tiktok} health={health?.tiktok} onAdvanced={() => setAdvancedOpen(true)}/>
        </div>
        {health && <div className="rounded-xl border border-line p-4 text-xs"><strong>Apify token</strong><span className="ml-2 text-muted">{health.apify?.status}</span></div>}
        <div className="rounded-xl border border-line">
          <button type="button" aria-expanded={advancedOpen} onClick={() => setAdvancedOpen(value => !value)} className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold">Advanced Settings <span aria-hidden className={`transition-transform ${advancedOpen ? "rotate-180" : ""}`}>⌄</span></button>
          {advancedOpen && <div className="grid gap-4 border-t border-line p-4 sm:grid-cols-2">
            <Field label="Instagram Actor Override" htmlFor="apify-instagram-actor"><Input id="apify-instagram-actor" value={instagramActor} onChange={event => setInstagramActor(event.target.value)} placeholder="Optional Actor ID"/><p className="text-xs leading-5 text-muted">Leave blank to use DINKLY Creative Studio’s recommended default.</p></Field>
            <Field label="TikTok Actor Override" htmlFor="apify-tiktok-actor"><Input id="apify-tiktok-actor" value={tiktokActor} onChange={event => setTiktokActor(event.target.value)} placeholder="Optional Actor ID"/><p className="text-xs leading-5 text-muted">Leave blank to use DINKLY Creative Studio’s recommended default.</p></Field>
          </div>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={saveProvider} disabled={busy}><Save className="size-4"/>Save securely</Button>
          <Button id="test-connection" variant="outline" onClick={testConnection} disabled={busy || !provider?.configured}><RefreshCw className="size-4"/>Test connection</Button>
          <Button variant="outline" onClick={() => document.getElementById("provider-usage")?.scrollIntoView({ behavior: "smooth" })}>View usage</Button>
          <Button variant="outline" onClick={pauseOrResume} disabled={busy || !provider?.configured}>{provider?.paused ? <Play className="size-4"/> : <Pause className="size-4"/>}{provider?.paused ? confirmResume ? "Confirm resume" : "Resume provider" : "Pause provider"}</Button>
          {provider?.configured && <Button variant="ghost" onClick={() => confirmRemove ? removeKey() : setConfirmRemove(true)} disabled={busy}><Trash2 className="size-4"/>{confirmRemove ? "Confirm remove key" : "Remove key"}</Button>}
        </div>
        {confirmResume && <p className="rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-900">Resuming may allow paid calls again. Select Confirm resume only after reviewing usage and connection health.</p>}
        {provider?.message && <p className="text-xs leading-5 text-muted">{provider.message}</p>}
      </CardContent>
    </Card>

    {budget && <Card id="provider-usage" className="border-black/[0.055] shadow-none">
      <CardHeader className="flex-row items-start justify-between gap-4"><div><CardTitle>Provider budget guardrails</CardTitle><p className="mt-1 text-sm leading-6 text-muted">Paid calls remain off until you explicitly enable them.</p></div>{usage && <div className="text-right text-xs text-muted"><strong className="block text-sm text-ink">${usage.monthly_used.toFixed(2)} of ${usage.monthly_budget.toFixed(2)}</strong>{usage.percent_remaining}% remaining</div>}</CardHeader>
      <CardContent className="space-y-5">
        {usage?.approaching_limit && <div className="flex gap-2 rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-900"><AlertTriangle className="mt-0.5 size-4 shrink-0"/>Approaching your monthly provider budget.</div>}
        {usage?.hard_limit_reached && <div className="flex gap-2 rounded-xl bg-red-50 p-3 text-xs leading-5 text-red-900"><Pause className="mt-0.5 size-4 shrink-0"/>Provider calls paused to prevent additional charges.</div>}
        <Toggle label="Enable paid provider calls" checked={budget.enable_paid_provider_calls} onChange={value => setBudget({ ...budget, enable_paid_provider_calls: value })}/>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <NumberField label="Maximum per run" value={budget.maximum_estimated_cost_per_run} onChange={value => setBudget({ ...budget, maximum_estimated_cost_per_run: value })} prefix="$"/>
          <NumberField label="Daily budget" value={budget.daily_provider_budget} onChange={value => setBudget({ ...budget, daily_provider_budget: value })} prefix="$"/>
          <NumberField label="Monthly budget" value={budget.monthly_provider_budget} onChange={value => setBudget({ ...budget, monthly_provider_budget: value })} prefix="$"/>
          <NumberField label="Confirm above" value={budget.require_confirmation_above_estimated_cost} onChange={value => setBudget({ ...budget, require_confirmation_above_estimated_cost: value })} prefix="$"/>
          <NumberField label="Maximum handles" value={budget.maximum_handles_per_refresh} onChange={value => setBudget({ ...budget, maximum_handles_per_refresh: value })}/>
          <NumberField label="Posts per handle" value={budget.maximum_posts_per_handle} onChange={value => setBudget({ ...budget, maximum_posts_per_handle: value })}/>
          <NumberField label="Requests per run" value={budget.maximum_provider_requests_per_run} onChange={value => setBudget({ ...budget, maximum_provider_requests_per_run: value })}/>
          <NumberField label="Maximum retries" value={budget.maximum_retries} onChange={value => setBudget({ ...budget, maximum_retries: value })}/>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <Toggle label="Pause at 80 percent" checked={budget.automatically_pause_at_80_percent} onChange={value => setBudget({ ...budget, automatically_pause_at_80_percent: value })}/>
          <Toggle label="Hard stop at 100 percent" checked={budget.hard_stop_at_100_percent} onChange={value => setBudget({ ...budget, hard_stop_at_100_percent: value })}/>
          <Toggle label="Allow paid overage" checked={budget.allow_paid_overage} onChange={value => setBudget({ ...budget, allow_paid_overage: value })}/>
        </div>
        {!compact && <details className="rounded-xl border border-line p-4"><summary className="cursor-pointer text-sm font-semibold">Scheduling and advanced timeouts</summary><div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Toggle label="Enable local schedule" checked={budget.schedule_enabled} onChange={value => setBudget({ ...budget, schedule_enabled: value })}/><Field label="Frequency"><Select value={budget.schedule_frequency} onChange={event => setBudget({ ...budget, schedule_frequency: event.target.value as ProviderBudgetSettings["schedule_frequency"] })}><option>Daily</option><option>Every 3 days</option><option>Weekly</option></Select></Field><NumberField label="Connection timeout" value={budget.connection_timeout_seconds} onChange={value => setBudget({ ...budget, connection_timeout_seconds: value })}/><NumberField label="Read timeout" value={budget.read_timeout_seconds} onChange={value => setBudget({ ...budget, read_timeout_seconds: value })}/><NumberField label="Download timeout" value={budget.download_timeout_seconds} onChange={value => setBudget({ ...budget, download_timeout_seconds: value })}/><NumberField label="Actor timeout" value={budget.actor_run_timeout_seconds} onChange={value => setBudget({ ...budget, actor_run_timeout_seconds: value })}/></div><p className="mt-3 text-xs leading-5 text-muted">Scheduled work runs only while the local worker or installed background service is active. A stopped computer is never awakened.</p></details>}
        <Button onClick={saveBudget} disabled={busy}><Save className="size-4"/>Save budget settings</Button>
      </CardContent>
    </Card>}
  </div>;
}

function ProviderState({ state }: { state: string }) {
  const good = state === "Configured";
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${good ? "bg-emerald-50 text-emerald-800" : state === "Not configured" ? "bg-wash text-muted" : "bg-amber-50 text-amber-900"}`}>{good ? <CheckCircle2 className="size-3"/> : <EyeOff className="size-3"/>}{state}</span>;
}

function Field({ label, children, htmlFor }: { label: string; children: React.ReactNode; htmlFor?: string }) { return <div className="space-y-1.5"><Label htmlFor={htmlFor}>{label}</Label>{children}</div>; }
function NumberField({ label, value, onChange, prefix }: { label: string; value: number; onChange: (value: number) => void; prefix?: string }) { return <Field label={label}><div className="relative">{prefix && <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs text-muted">{prefix}</span>}<Input type="number" min={0} step={Number.isInteger(value) ? 1 : 0.1} value={value} onChange={event => onChange(Number(event.target.value))} className={prefix ? "pl-7" : ""}/></div></Field>; }
function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) { return <label className="flex min-h-11 items-center justify-between gap-3 rounded-xl border border-line bg-white px-3 py-2 text-xs font-semibold"><span>{label}</span><input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} className="size-4 accent-black"/></label>; }

function PlatformCard({ name, enabled, onChange, status, health, onAdvanced }: { name: string; enabled: boolean; onChange: (value: boolean) => void; status?: { source: string; last_verified_at: string | null; verification_status: string }; health?: { status: string; ready?: boolean; message?: string }; onAdvanced: () => void }) {
  const unavailable = health && health.ready === false;
  return <div className="rounded-2xl border border-line bg-white p-4">
    <div className="flex items-center justify-between"><strong className="text-sm">{name}</strong><label className="flex items-center gap-2 text-xs font-semibold"><span>{enabled ? "Enabled" : "Disabled"}</span><input aria-label={`${name} enabled`} type="checkbox" checked={enabled} onChange={event => onChange(event.target.checked)} className="size-4 accent-black"/></label></div>
    <p className={`mt-2 text-xs ${unavailable ? "text-red-700" : "text-muted"}`}>{unavailable ? "Default Actor unavailable" : status?.source === "override" ? "Using custom Actor" : "Using recommended Actor"}</p>
    <p className="mt-1 text-[11px] text-muted">Last verified: {status?.last_verified_at ? new Date(status.last_verified_at).toLocaleDateString() : "Not yet verified"}</p>
    {unavailable && <div className="mt-3 flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" onClick={() => document.getElementById("test-connection")?.click()}>Retry</Button><Button type="button" size="sm" variant="ghost" onClick={onAdvanced}>Choose another Actor</Button></div>}
  </div>;
}
