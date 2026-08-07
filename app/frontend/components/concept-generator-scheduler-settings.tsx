"use client";

import { AlertTriangle, CheckCircle2, Clock3, Play, RefreshCw, Save, Wrench } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";

interface SchedulerSettings {
  generate_daily_automatically: boolean;
  run_time: string;
  timezone: string;
  schedule_days: "every_day" | "weekdays";
  catch_up_on_wake: boolean;
  catch_up_on_start: boolean;
  generate_on_start: boolean;
  enable_paid_model_calls: boolean;
  maximum_automatic_batch_cost: number;
  maximum_manual_batch_cost: number;
  daily_model_budget: number;
  monthly_model_budget: number;
  last_scheduler_check: string | null;
}

interface Diagnostic {
  ready: boolean;
  verdict: string;
  checked_at: string;
  problems: string[];
  scheduler: Record<string, any>;
  background_worker: Record<string, any>;
  ai_provider: Record<string, any>;
  provider_health: string;
  budget: Record<string, number>;
  today_batch_status: string;
  duplicate_protection: string;
}

interface ProviderStatus { configured: boolean; masked_token?: string | null; model: string; source?: string | null; runtime?: Record<string, any> }
interface Logs { stdout: string[]; stderr: string[] }

export function ConceptGeneratorSchedulerSettings() {
  const [settings, setSettings] = useState<SchedulerSettings>();
  const [diagnostic, setDiagnostic] = useState<Diagnostic>();
  const [provider, setProvider] = useState<ProviderStatus>();
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("gpt-5.6-luna");
  const [logs, setLogs] = useState<Logs>();
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());

  const load = useCallback(async () => {
    const [nextSettings, nextDiagnostic, nextProvider] = await Promise.all([
      api<SchedulerSettings>("/api/concept-generator/settings"),
      api<Diagnostic>("/api/concept-generator/scheduler/diagnostic"),
      api<ProviderStatus>("/api/concept-generator/provider"),
    ]);
    setSettings(nextSettings);
    setDiagnostic(nextDiagnostic);
    setProvider(nextProvider);
    setModel(nextProvider.model || "gpt-5.6-luna");
  }, []);

  useEffect(() => { load().catch(error => toast.error(error.message)); }, [load]);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);

  async function action<T>(work: () => Promise<T>, success?: string) {
    setBusy(true);
    try { const result = await work(); if (success) toast.success(success); await load(); return result; }
    catch (error) { toast.error(error instanceof Error ? error.message : "Scheduler action failed"); }
    finally { setBusy(false); }
  }

  async function save() {
    if (!settings) return;
    await action(() => api("/api/concept-generator/settings", { method: "PUT", body: JSON.stringify({ ...settings, last_scheduler_check: null }) }), "Scheduler settings saved");
  }

  async function saveProvider() {
    if (!apiKey.trim()) { toast.error("Enter an OpenAI API key first"); return; }
    await action(() => api("/api/concept-generator/provider", { method: "PUT", body: JSON.stringify({ api_key: apiKey, model }) }), "OpenAI provider saved for the app and background agent");
    setApiKey("");
  }

  async function background(command: "install" | "start" | "restart") {
    await action(() => api(`/api/concept-generator/background-agent/${command}`, { method: "POST", body: "{}" }), `Background agent ${command} requested`);
  }

  async function scheduleTest() {
    const result = await action(() => api<{ scheduled: boolean; message?: string }>("/api/concept-generator/scheduler/test", { method: "POST", body: "{}" }));
    if (result?.scheduled) toast.success("Real supplemental scheduler test set for two minutes from now");
    else if (result?.message) toast.error(result.message);
  }

  async function testProvider() {
    setBusy(true);
    try {
      const result = await api<{ connected: boolean; message: string }>("/api/concept-generator/provider/test", { method: "POST", body: "{}" });
      if (result.connected) toast.success(result.message || "OpenAI model responded");
      else toast.error(result.message || "OpenAI connection test failed");
      await load();
    } catch (error) { toast.error(error instanceof Error ? error.message : "OpenAI connection test failed"); }
    finally { setBusy(false); }
  }

  if (!settings || !diagnostic || !provider) return <Card id="concept-generator-scheduler"><CardContent className="p-6 text-sm text-muted">Checking Concept Generator automation…</CardContent></Card>;
  const due = diagnostic.scheduler.test_scheduled_for ? new Date(diagnostic.scheduler.test_scheduled_for).getTime() : null;
  const countdown = due && due > now ? Math.ceil((due - now) / 1000) : null;

  return <section id="concept-generator-scheduler" className="scroll-mt-8 space-y-4">
    <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-muted">Agents · Concept Generator</p><h2 className="mt-2 font-display text-2xl font-semibold">Scheduler</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-muted">The LaunchAgent runs independently of the browser. This diagnostic never makes an AI call; connection testing and the two-minute test are explicit actions.</p></div>

    <Card className={diagnostic.ready ? "border-emerald-200" : "border-amber-300"}>
      <CardHeader><CardTitle className="flex items-center gap-2">{diagnostic.ready ? <CheckCircle2 className="size-5 text-emerald-700"/> : <AlertTriangle className="size-5 text-amber-700"/>}{diagnostic.verdict}</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Status label="Scheduler" value={settings.generate_daily_automatically ? "Enabled" : "Disabled"} good={settings.generate_daily_automatically}/>
          <Status label="Background worker" value={diagnostic.background_worker.status} good={diagnostic.background_worker.running}/>
          <Status label="AI provider" value={provider.configured ? `${provider.model} configured` : "Not configured"} good={provider.configured}/>
          <Status label="Budget" value={`$${diagnostic.budget.daily_remaining.toFixed(2)} today`} good={diagnostic.budget.daily_remaining >= settings.maximum_automatic_batch_cost}/>
          <Status label="Timezone" value={settings.timezone} good/>
          <Status label="Scheduled time" value={settings.run_time} good/>
          <Status label="Next run" value={formatDate(diagnostic.scheduler.next_run)} good={settings.generate_daily_automatically}/>
          <Status label="Last attempt" value={formatDate(diagnostic.scheduler.last_attempted_run)} good={diagnostic.scheduler.last_status !== "Failed"}/>
          <Status label="Last success" value={formatDate(diagnostic.scheduler.last_successful_run)} good={Boolean(diagnostic.scheduler.last_successful_run)}/>
          <Status label="Last failure" value={diagnostic.scheduler.last_failure ? `${formatDate(diagnostic.scheduler.last_failure_at)} · ${diagnostic.scheduler.last_failure}` : "None"} good={!diagnostic.scheduler.last_failure}/>
          <Status label="Last skip" value={diagnostic.scheduler.last_skip ? `${formatDate(diagnostic.scheduler.last_skip_at)} · ${diagnostic.scheduler.last_skip}` : "None"} good={!diagnostic.scheduler.last_skip}/>
          <Status label="Provider health" value={diagnostic.provider_health} good={provider.configured}/>
          <Status label="Today" value={diagnostic.today_batch_status} good={diagnostic.today_batch_status !== "failed"}/>
          <Status label="Duplicate protection" value={diagnostic.duplicate_protection} good/>
        </div>
        {diagnostic.problems.length > 0 && <ul className="rounded-xl bg-amber-50 p-4 text-xs leading-6 text-amber-950">{diagnostic.problems.map(problem => <li key={problem}>• {problem}</li>)}</ul>}
        <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => action(load, "Diagnostic refreshed")} disabled={busy}><RefreshCw className="size-4"/>Run Scheduler Diagnostic</Button>{!diagnostic.background_worker.installed && <Button size="sm" variant="outline" onClick={() => background("install")} disabled={busy}><Wrench className="size-4"/>Install Background Agent</Button>}{diagnostic.background_worker.installed && !diagnostic.background_worker.running && <Button size="sm" variant="outline" onClick={() => background("start")} disabled={busy}><Play className="size-4"/>Start</Button>}{diagnostic.background_worker.installed && <Button size="sm" variant="outline" onClick={() => background("restart")} disabled={busy}><RefreshCw className="size-4"/>Restart</Button>}<Button size="sm" variant="ghost" onClick={async () => setLogs(await api<Logs>("/api/concept-generator/background-agent/logs"))}>View Logs</Button></div>
        {logs && <div className="grid gap-3 lg:grid-cols-2"><Log title="Worker log" lines={logs.stdout}/><Log title="Errors" lines={logs.stderr}/></div>}
      </CardContent>
    </Card>

    <div className="grid gap-5 lg:grid-cols-2">
      <Card><CardHeader><CardTitle>Daily schedule</CardTitle></CardHeader><CardContent className="space-y-4">
        <Toggle label="Automatic daily generation" checked={settings.generate_daily_automatically} onChange={value => setSettings({ ...settings, generate_daily_automatically: value })}/>
        <div className="grid gap-3 sm:grid-cols-2"><Field label="Local time"><Input type="time" value={settings.run_time} onChange={event => setSettings({ ...settings, run_time: event.target.value })}/></Field><Field label="IANA timezone"><Input value={settings.timezone} onChange={event => setSettings({ ...settings, timezone: event.target.value })}/></Field></div>
        <Field label="Schedule days"><Select value={settings.schedule_days} onChange={event => setSettings({ ...settings, schedule_days: event.target.value as SchedulerSettings["schedule_days"] })}><option value="every_day">Every day</option><option value="weekdays">Weekdays</option></Select></Field>
        <Toggle label="Catch up when Mac wakes" checked={settings.catch_up_on_wake} onChange={value => setSettings({ ...settings, catch_up_on_wake: value })}/>
        <Toggle label="Catch up when app starts" checked={settings.catch_up_on_start} onChange={value => setSettings({ ...settings, catch_up_on_start: value })}/>
        <Toggle label="Allow paid model calls automatically" checked={settings.enable_paid_model_calls} onChange={value => setSettings({ ...settings, enable_paid_model_calls: value })}/>
        <div className="grid gap-3 sm:grid-cols-3"><Money label="Max automatic batch" value={settings.maximum_automatic_batch_cost} onChange={value => setSettings({ ...settings, maximum_automatic_batch_cost: value })}/><Money label="Daily budget" value={settings.daily_model_budget} onChange={value => setSettings({ ...settings, daily_model_budget: value })}/><Money label="Monthly budget" value={settings.monthly_model_budget} onChange={value => setSettings({ ...settings, monthly_model_budget: value })}/></div>
        <Button onClick={save} disabled={busy}><Save className="size-4"/>Save Scheduler</Button>
      </CardContent></Card>

      <Card><CardHeader><CardTitle>OpenAI provider</CardTitle></CardHeader><CardContent className="space-y-4">
        <p className="text-xs leading-5 text-muted">{provider.configured ? `${provider.masked_token} · loaded from ${provider.source}` : "No production AI key is configured. Scheduled runs will skip truthfully."}</p>
        <Field label="API key"><Input type="password" autoComplete="off" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder={provider.configured ? "Enter only to replace the saved key" : "sk-…"}/></Field>
        <Field label="Model"><Input value={model} onChange={event => setModel(event.target.value)}/></Field>
        <div className="flex flex-wrap gap-2"><Button onClick={saveProvider} disabled={busy || !apiKey.trim()}>Save Provider</Button><Button variant="outline" onClick={testProvider} disabled={busy || !provider.configured}>Test Connection</Button></div>
      </CardContent></Card>
    </div>

    <Card><CardHeader><CardTitle className="flex items-center gap-2"><Clock3 className="size-5"/>Test 8 AM Automation</CardTitle></CardHeader><CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center"><div className="flex-1"><p className="text-sm font-semibold">Run the actual worker and production workflow in two minutes.</p><p className="mt-1 text-xs leading-5 text-muted">It uses the real provider and saves a supplemental batch, so today’s primary data is never overwritten. The browser may close after scheduling.</p><p className="mt-2 text-xs font-semibold">Status: {diagnostic.scheduler.test_status}{countdown !== null ? ` · ${Math.floor(countdown / 60)}:${String(countdown % 60).padStart(2, "0")}` : ""}{diagnostic.scheduler.test_error ? ` · ${diagnostic.scheduler.test_error}` : ""}</p></div><Button onClick={scheduleTest} disabled={busy || !diagnostic.ready || diagnostic.scheduler.test_status === "Running"}><Play className="size-4"/>Run 2-Minute Scheduler Test</Button></CardContent></Card>
  </section>;
}

function Status({ label, value, good }: { label: string; value: string; good: boolean }) { return <div className="rounded-xl border border-line p-3"><p className="text-[9px] font-bold uppercase tracking-wide text-muted">{label}</p><p className={`mt-1 text-xs font-semibold ${good ? "text-ink" : "text-amber-800"}`}>{value}</p></div>; }
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <div className="space-y-1.5"><Label>{label}</Label>{children}</div>; }
function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) { return <label className="flex items-center justify-between rounded-xl border border-line p-3 text-sm"><span>{label}</span><input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} className="size-4 accent-black"/></label>; }
function Money({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) { return <Field label={label}><div className="relative"><span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted">$</span><Input className="pl-7" type="number" min="0" step="0.1" value={value} onChange={event => onChange(Number(event.target.value))}/></div></Field>; }
function Log({ title, lines }: { title: string; lines: string[] }) { return <div className="min-w-0 rounded-xl bg-[#171914] p-3 text-white"><p className="text-[10px] font-bold uppercase tracking-wide text-white/60">{title}</p><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-[10px] leading-5">{lines.length ? lines.join("\n") : "No entries yet."}</pre></div>; }
function formatDate(value?: string | null) { return value ? new Date(value).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "Never"; }
