"use client";

import {
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  Check,
  CirclePlus,
  Clock3,
  Eye,
  FileUp,
  Lightbulb,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Settings,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { AgentAvatar } from "@/components/agent-avatar";
import { SocialProviderSettings } from "@/components/social-provider-settings";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  API_URL,
  api,
  getAgentRuns,
  getCompetitorDirections,
  getCompetitorLearnings,
  getCompetitorPosts,
  getMonitoredHandles,
  getProviderPreflight,
  getSocialDataProviders,
} from "@/lib/api";
import { agentById } from "@/lib/agents";
import type {
  AgentEvent,
  AgentRun,
  CompetitorDirection,
  CompetitorLearning,
  CompetitorPost,
  MonitoredHandle,
  ProviderPreflight,
  SocialProviderStatus,
} from "@/lib/types";

type WorkspaceTab = "handles" | "live" | "posts" | "learnings" | "directions" | "runs" | "settings";
type BulkPreview = { handles: Array<{ platform: string; username: string; canonical_url: string; duplicate: boolean; category: string }>; count: number };
type PostFilters = { platform: string; handle: string; media: string; theme: string; format: string; date: string; percentile: string; classified: string; completeness: string };
type BudgetState = { settings: { enable_paid_provider_calls: boolean }; usage: { monthly_used: number; monthly_remaining: number; monthly_budget: number; percent_remaining: number; approaching_limit: boolean; hard_limit_reached: boolean } };

const eventKinds = ["run", "preflight", "scope", "budget", "provider-request", "deduplication", "budget-stop", "provider-warning", "analysis", "complete", "cancellation", "recovery"];
const socialAgent = agentById("social-intelligence")!;

export default function SocialIntelligencePage() {
  const router = useRouter();
  const sourceRef = useRef<EventSource | null>(null);
  const [tab, setTab] = useState<WorkspaceTab>("handles");
  const [providers, setProviders] = useState<SocialProviderStatus[]>([]);
  const [handles, setHandles] = useState<MonitoredHandle[]>([]);
  const [posts, setPosts] = useState<CompetitorPost[]>([]);
  const [learnings, setLearnings] = useState<CompetitorLearning[]>([]);
  const [directions, setDirections] = useState<CompetitorDirection[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [budgetState, setBudgetState] = useState<BudgetState>();
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [activeRun, setActiveRun] = useState<AgentRun>();
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [preflight, setPreflight] = useState<ProviderPreflight>();
  const [refreshHandleIds, setRefreshHandleIds] = useState<string[]>([]);
  const [preflightOpen, setPreflightOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkText, setBulkText] = useState("");
  const [bulkPlatform, setBulkPlatform] = useState("");
  const [bulkCategory, setBulkCategory] = useState("Other");
  const [bulkPreview, setBulkPreview] = useState<BulkPreview>();
  const [filters, setFilters] = useState<PostFilters>({ platform: "all", handle: "all", media: "all", theme: "", format: "all", date: "", percentile: "all", classified: "all", completeness: "all" });

  const load = useCallback(async () => {
    try {
      const [providerData, handleData, postData, learningData, directionData, runData, budgetData] = await Promise.all([
        getSocialDataProviders(), getMonitoredHandles(), getCompetitorPosts(), getCompetitorLearnings(), getCompetitorDirections(), getAgentRuns(), api<BudgetState>("/api/provider-budget"),
      ]);
      setProviders(providerData);
      setHandles(handleData);
      setPosts(postData);
      setLearnings(learningData);
      setDirections(directionData);
      setRuns(runData);
      setBudgetState(budgetData);
      const current = runData.find(item => item.status === "Running");
      if (current) connectToRun(current);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Social Intelligence data could not be loaded");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    return () => sourceRef.current?.close();
  }, [load]);

  const apify = providers.find(item => item.name === "Apify");
  const enabledHandles = handles.filter(item => item.enabled);
  const approvedLearnings = learnings.filter(item => item.status === "Approved").length;
  const filteredPosts = useMemo(() => posts.filter(post => {
    const theme = String(post.creative_attributes?.theme ?? post.creative_attributes?.emotional_theme ?? "").toLowerCase();
    const format = String(post.creative_attributes?.format ?? "");
    const classified = Boolean(post.creative_attributes?.classification_source);
    const percentile = post.performance.percentile_rank;
    return (filters.platform === "all" || post.platform === filters.platform)
      && (filters.handle === "all" || post.handle_id === filters.handle)
      && (filters.media === "all" || (post.media_type ?? "Unavailable") === filters.media)
      && (!filters.theme || theme.includes(filters.theme.toLowerCase()))
      && (filters.format === "all" || format === filters.format)
      && (!filters.date || Boolean(post.posted_at && post.posted_at.slice(0, 10) >= filters.date))
      && (filters.percentile === "all" || (percentile !== null && percentile >= Number(filters.percentile)))
      && (filters.classified === "all" || (filters.classified === "yes" ? classified : !classified))
      && (filters.completeness === "all" || (filters.completeness === "complete" ? post.metric_completeness.percent === 1 : post.metric_completeness.percent < 1));
  }), [posts, filters]);

  function connectToRun(run: AgentRun) {
    sourceRef.current?.close();
    setActiveRun(run);
    setEvents([]);
    setTab("live");
    const source = new EventSource(`${API_URL}/api/agent-runs/${run.id}/events`);
    sourceRef.current = source;
    const receive = (message: MessageEvent) => {
      const event = JSON.parse(message.data) as AgentEvent;
      setEvents(previous => previous.some(item => item.id === event.id) ? previous : [...previous, event]);
      if (event.kind === "complete") {
        source.close();
        setWorking(false);
        load();
      }
    };
    eventKinds.forEach(kind => source.addEventListener(kind, receive as EventListener));
    source.onerror = () => {
      source.close();
      setWorking(false);
    };
  }

  async function previewRefresh(handleIds?: string[]) {
    setWorking(true);
    try {
      const selected = handleIds?.length ? handleIds : enabledHandles.map(item => item.id);
      setRefreshHandleIds(selected);
      const result = await getProviderPreflight({ handle_ids: selected });
      setPreflight(result);
      setPreflightOpen(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Preflight could not be prepared");
    } finally {
      setWorking(false);
    }
  }

  async function startRefresh() {
    if (!preflight?.can_run) return;
    setWorking(true);
    try {
      const result = await api<{ run: AgentRun }>("/api/monitored-handles/refresh", {
        method: "POST",
        body: JSON.stringify({ handle_ids: refreshHandleIds, confirmed: true }),
      });
      setPreflightOpen(false);
      connectToRun(result.run);
      toast.success("Provider refresh started");
    } catch (error) {
      setWorking(false);
      toast.error(error instanceof Error ? error.message : "Refresh could not start");
    }
  }

  async function analyzeExisting() {
    setWorking(true);
    try {
      const result = await api<{ learnings_created: number; directions_created?: number }>("/api/competitor-analysis", { method: "POST" });
      await load();
      setTab("learnings");
      toast.success(result.learnings_created ? `${result.learnings_created} evidence-based learning${result.learnings_created === 1 ? "" : "s"} created` : "Analysis complete; no supported new learning yet");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Analysis failed safely");
    } finally {
      setWorking(false);
    }
  }

  async function previewBulk() {
    if (!bulkText.trim()) return;
    setWorking(true);
    try {
      const payload = { text: bulkText, default_platform: bulkPlatform || null, category: bulkCategory };
      setBulkPreview(await api<BulkPreview>("/api/monitored-handles/bulk/preview", { method: "POST", body: JSON.stringify(payload) }));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Handles could not be parsed");
    } finally {
      setWorking(false);
    }
  }

  async function saveBulk() {
    setWorking(true);
    try {
      const payload = { text: bulkText, default_platform: bulkPlatform || null, category: bulkCategory };
      const result = await api<{ created: number }>("/api/monitored-handles/bulk", { method: "POST", body: JSON.stringify(payload) });
      setBulkOpen(false); setBulkText(""); setBulkPreview(undefined);
      await load();
      toast.success(`${result.created} monitored handle${result.created === 1 ? "" : "s"} added`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Handles could not be saved");
    } finally {
      setWorking(false);
    }
  }

  async function updateHandle(handle: MonitoredHandle, changes: Record<string, unknown>) {
    try {
      await api(`/api/monitored-handles/${handle.id}`, { method: "PUT", body: JSON.stringify(changes) });
      await load();
    } catch (error) { toast.error(error instanceof Error ? error.message : "Handle could not be updated"); }
  }

  async function validateHandles(handleIds: string[]) {
    try {
      const result = await api<Array<{ valid: boolean }>>("/api/monitored-handles/validate", { method: "POST", body: JSON.stringify({ handle_ids: handleIds }) });
      const valid = result.filter(item => item.valid).length;
      toast.success(`${valid} of ${result.length} handle formats validated`);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Handles could not be validated"); }
  }

  async function removeHandle(handle: MonitoredHandle) {
    if (!window.confirm(`Stop monitoring @${handle.username}? Historical posts and learnings will be preserved.`)) return;
    try {
      await api(`/api/monitored-handles/${handle.id}`, { method: "DELETE" });
      await load();
      toast.success("Monitoring removed; history preserved");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Handle could not be removed"); }
  }

  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData(); form.append("file", file);
    setWorking(true);
    try {
      const result = await api<{ posts_created: number; posts_skipped: number }>("/api/competitor-posts/import", { method: "POST", body: form });
      await load();
      setTab("posts");
      toast.success(`${result.posts_created} posts imported; ${result.posts_skipped} duplicates skipped`);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Import failed"); }
    finally { setWorking(false); event.target.value = ""; }
  }

  async function decideLearning(learning: CompetitorLearning, decision: "approve" | "reject") {
    try {
      await api(`/api/competitor-learnings/${learning.id}/${decision}`, { method: "POST", body: JSON.stringify({ notes: "" }) });
      await load();
      toast.success(`Learning ${decision === "approve" ? "approved" : "rejected"}`);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Learning could not be updated"); }
  }

  async function generateDirections() {
    const learningIds = learnings.filter(item => item.status === "Approved").map(item => item.id);
    setWorking(true);
    try {
      const result = await api<{ created: number }>("/api/competitor-concepts/generate", { method: "POST", body: JSON.stringify({ learning_ids: learningIds, limit: 3 }) });
      await load();
      setTab("directions");
      toast.success(`${result.created} original DINKLY direction${result.created === 1 ? "" : "s"} created`);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Directions need more approved evidence"); }
    finally { setWorking(false); }
  }

  async function openDirection(direction: CompetitorDirection) {
    setWorking(true);
    try {
      const result = await api<{ href: string }>(`/api/competitor-concepts/${direction.id}/open-in-prompt-builder`, { method: "POST" });
      router.push(result.href);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Direction could not be handed off"); setWorking(false); }
  }

  async function cancelRun() {
    if (!activeRun) return;
    await api(`/api/agent-runs/${activeRun.id}/cancel`, { method: "POST" });
    toast.success("Cancellation requested");
  }

  return <div className="space-y-6">
    <section className="overflow-hidden rounded-[28px] border border-black/[0.055] bg-[#e3e5f3] p-6 sm:p-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-start gap-4"><AgentAvatar agentId="social-intelligence" size="lg" priority showStatus status={working ? "working" : "online"} className="ring-4 ring-white/70"/><div><p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#53627a]">{socialAgent.role}</p><h1 className="mt-1 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">{socialAgent.displayName}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-[#4e5969]">{socialAgent.personality}</p></div></div>
        <div className="flex flex-wrap gap-2"><Button onClick={() => previewRefresh()} disabled={working || enabledHandles.length === 0}><RefreshCw className={working ? "size-4 animate-spin" : "size-4"}/>Refresh handles</Button><Button variant="outline" onClick={analyzeExisting} disabled={working || posts.length === 0}><BarChart3 className="size-4"/>Analyze existing data</Button><Button variant="outline" onClick={() => setBulkOpen(true)}><CirclePlus className="size-4"/>Add handles</Button><label className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl border border-line bg-white px-4 text-sm font-semibold hover:bg-wash"><FileUp className="size-4"/>Import data<input aria-label="Import data" className="sr-only" type="file" accept=".csv,.json,application/json,text/csv" onChange={importFile}/></label><Button variant="ghost" onClick={() => setTab("settings")}><Settings className="size-4"/>Provider settings</Button></div>
      </div>
    </section>

    <StatusStrip provider={apify} budget={budgetState} handles={handles.length} posts={posts.length} approved={approvedLearnings}/>

    {!loading && !apify?.configured && posts.length === 0 && <FirstRun onAdd={() => setBulkOpen(true)} onSettings={() => setTab("settings")}/>} 
    {!loading && apify?.configured && !budgetState?.settings.enable_paid_provider_calls && <Card className="border-amber-200 bg-amber-50 shadow-none"><CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-semibold text-amber-950">Apify is connected. Enable paid provider calls and set a budget before refreshing handles.</p><p className="mt-1 text-sm text-amber-900">Manual import and analysis remain available.</p></div><Button variant="outline" onClick={() => setTab("settings")}>Review safe defaults</Button></CardContent></Card>}

    <Tabs value={tab} onValueChange={value => setTab(value as WorkspaceTab)}>
      <TabsList className="max-w-full flex-wrap"><TabsTrigger value="handles">Handles</TabsTrigger><TabsTrigger value="live">Live Work</TabsTrigger><TabsTrigger value="posts">Posts</TabsTrigger><TabsTrigger value="learnings">Learnings</TabsTrigger><TabsTrigger value="directions">Concept Directions</TabsTrigger><TabsTrigger value="runs">Runs</TabsTrigger><TabsTrigger value="settings">Settings</TabsTrigger></TabsList>

      <TabsContent value="handles"><HandlesTab handles={handles} loading={loading} onAdd={() => setBulkOpen(true)} onUpdate={updateHandle} onDelete={removeHandle} onRefresh={previewRefresh} onValidate={validateHandles}/></TabsContent>
      <TabsContent value="live"><LiveWork run={activeRun ?? runs.find(item => item.status === "Running")} events={events} onCancel={cancelRun}/></TabsContent>
      <TabsContent value="posts"><PostsTab posts={filteredPosts} allPosts={posts} handles={handles} filters={filters} setFilters={setFilters} onChange={load}/></TabsContent>
      <TabsContent value="learnings"><LearningsTab learnings={learnings} posts={posts} onDecision={decideLearning} onAnalyze={analyzeExisting}/></TabsContent>
      <TabsContent value="directions"><DirectionsTab directions={directions} approvedLearnings={approvedLearnings} onGenerate={generateDirections} onOpen={openDirection}/></TabsContent>
      <TabsContent value="runs"><RunsTab runs={runs} onOpen={connectToRun}/></TabsContent>
      <TabsContent value="settings"><SocialProviderSettings onChange={load}/></TabsContent>
    </Tabs>

    <Dialog open={bulkOpen} onOpenChange={setBulkOpen}><DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Add monitored handles</DialogTitle><DialogDescription>Paste one handle or public profile URL per line. Use platform,@handle when the lines mix Instagram and TikTok.</DialogDescription></DialogHeader><div className="space-y-4"><Field label="Handles or profile URLs"><Textarea rows={7} value={bulkText} onChange={event => { setBulkText(event.target.value); setBulkPreview(undefined); }} placeholder={"instagram,@example\nhttps://www.tiktok.com/@another"}/></Field><label className="inline-flex cursor-pointer items-center gap-2 text-xs font-semibold text-muted hover:text-ink"><FileUp className="size-4"/>Import handle lines from CSV or text<input type="file" accept=".csv,.txt,text/csv,text/plain" className="sr-only" onChange={async event => { const file = event.target.files?.[0]; if (file) { setBulkText(await file.text()); setBulkPreview(undefined); } }}/></label><div className="grid gap-4 sm:grid-cols-2"><Field label="Default platform"><Select value={bulkPlatform} onChange={event => setBulkPlatform(event.target.value)}><option value="">Read platform from each line</option><option value="instagram">Instagram</option><option value="tiktok">TikTok</option></Select></Field><Field label="Category"><Select value={bulkCategory} onChange={event => setBulkCategory(event.target.value)}>{["Other", "Owned account", "Direct competitor", "Inspiration", "Publisher", "Character IP", "Relationship content", "Illustration", "Brand", "Trend account"].map(value => <option key={value}>{value}</option>)}</Select></Field></div>{bulkPreview && <div className="max-h-52 overflow-auto rounded-xl border border-line">{bulkPreview.handles.map(item => <div key={`${item.platform}-${item.username}`} className="flex items-center justify-between border-b border-line px-3 py-2 text-sm last:border-0"><span><strong>@{item.username}</strong> <span className="text-muted">· {item.platform}</span></span>{item.duplicate && <Badge>Already monitored</Badge>}</div>)}</div>}<div className="flex justify-end gap-2"><Button variant="outline" onClick={previewBulk} disabled={working || !bulkText.trim()}>{bulkPreview ? "Preview again" : "Preview handles"}</Button><Button onClick={saveBulk} disabled={working || !bulkPreview || bulkPreview.handles.every(item => item.duplicate)}>Save new handles</Button></div></div></DialogContent></Dialog>

    <Dialog open={preflightOpen} onOpenChange={setPreflightOpen}><DialogContent className="max-w-xl"><DialogHeader><DialogTitle>Provider preflight</DialogTitle><DialogDescription>Nothing runs until you review the scope and cost boundary.</DialogDescription></DialogHeader>{preflight && <div className="space-y-4"><div className="grid grid-cols-2 gap-3"><Stat label="Handles" value={String(preflight.handles)}/><Stat label="Maximum posts" value={String(preflight.maximum_posts)}/><Stat label="Estimated range" value={costRange(preflight)}/><Stat label="Provider health" value={preflight.provider_health ?? "Unknown"}/><Stat label="Daily remaining" value={moneyOrUnavailable(preflight.daily_budget_remaining)}/><Stat label="Monthly remaining" value={moneyOrUnavailable(preflight.monthly_budget_remaining)}/></div>{preflight.warnings.length > 0 && <Notice tone="warning" items={preflight.warnings}/>} {preflight.hard_stops.length > 0 && <Notice tone="danger" items={preflight.hard_stops}/>}<p className="text-xs leading-5 text-muted">{preflight.estimated_cost_label ?? "Actual cost remains unavailable unless the provider reports it."}</p><div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setPreflightOpen(false)}>Cancel</Button><Button variant="outline" onClick={() => { setPreflightOpen(false); setBulkOpen(true); }}>Reduce scope</Button><Button onClick={startRefresh} disabled={working || !preflight.can_run}>{preflight.requires_confirmation ? "Confirm and run" : "Run refresh"}</Button></div></div>}</DialogContent></Dialog>
  </div>;
}

function StatusStrip({ provider, budget, handles, posts, approved }: { provider?: SocialProviderStatus; budget?: BudgetState; handles: number; posts: number; approved: number }) {
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6"><MiniStatus label="Provider" value={provider?.state ?? "Checking"}/><MiniStatus label="Monitored" value={`${handles} handles`}/><MiniStatus label="Public evidence" value={`${posts} posts`}/><MiniStatus label="Approved learnings" value={String(approved)}/><MiniStatus label="Apify this month" value={budget ? `$${budget.usage.monthly_used.toFixed(2)} of $${budget.usage.monthly_budget.toFixed(2)} · ${budget.usage.percent_remaining}% left` : "Unavailable"}/><MiniStatus label="Last refresh" value={provider?.last_success_at ? dateOrNever(provider.last_success_at) : "Never"}/></div>;
}

function FirstRun({ onAdd, onSettings }: { onAdd: () => void; onSettings: () => void }) {
  return <Card className="border-dashed shadow-none"><CardContent className="flex flex-col items-start gap-5 p-7 sm:flex-row sm:items-center sm:justify-between"><div className="flex gap-4"><div className="rounded-2xl bg-[#e3e5f3] p-3"><Eye className="size-5 text-[#53627a]"/></div><div><h2 className="font-semibold">Connect a provider or import data manually.</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-muted">No provider call or fake record is created. Add Apify when you are ready, or import real public CSV/JSON data and analyze it now.</p></div></div><div className="flex shrink-0 gap-2"><Button variant="outline" onClick={onAdd}>Add handles</Button><Button onClick={onSettings}>Add Apify API key</Button></div></CardContent></Card>;
}

function HandlesTab({ handles, loading, onAdd, onUpdate, onDelete, onRefresh, onValidate }: { handles: MonitoredHandle[]; loading: boolean; onAdd: () => void; onUpdate: (handle: MonitoredHandle, changes: Record<string, unknown>) => void; onDelete: (handle: MonitoredHandle) => void; onRefresh: (ids?: string[]) => void; onValidate: (ids: string[]) => void }) {
  const [selected, setSelected] = useState<string[]>([]);
  const targetIds = selected.length ? selected : handles.filter(item => item.enabled).map(item => item.id);
  return <Card><CardHeader className="flex-row items-start justify-between"><div><CardTitle>Monitored public handles</CardTitle><p className="mt-1 text-sm text-muted">Monitoring configuration is separate from historical evidence. Removing a handle never deletes collected records.</p></div><div className="flex flex-wrap gap-2"><Button variant="outline" size="sm" onClick={() => onValidate(targetIds)} disabled={targetIds.length === 0}><Check className="size-4"/>Validate</Button><Button variant="outline" size="sm" onClick={() => onRefresh(targetIds)} disabled={targetIds.length === 0}><RefreshCw className="size-4"/>Refresh {selected.length ? "selected" : "all"}</Button><Button size="sm" onClick={onAdd}><CirclePlus className="size-4"/>Add</Button></div></CardHeader><CardContent>{loading ? <Empty icon={Loader2} title="Loading handles" text="Reading local monitoring records…"/> : handles.length === 0 ? <Empty icon={Eye} title="No monitored handles" text="Add Instagram or TikTok handles, or use manual import without a provider." action={<Button onClick={onAdd}>Add handles</Button>}/> : <Table><TableHeader><TableRow><TableHead><span className="sr-only">Select</span></TableHead><TableHead>Handle</TableHead><TableHead>Category</TableHead><TableHead>Posts</TableHead><TableHead>Schedule</TableHead><TableHead>Last success</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader><TableBody>{handles.map(handle => <TableRow key={handle.id}><TableCell><input type="checkbox" checked={selected.includes(handle.id)} onChange={event => setSelected(previous => event.target.checked ? [...previous, handle.id] : previous.filter(id => id !== handle.id))} className="size-4 accent-black"/></TableCell><TableCell><a href={handle.canonical_url} target="_blank" rel="noreferrer" className="font-semibold hover:underline">@{handle.username}</a><p className="mt-1 text-xs capitalize text-muted">{handle.platform}</p></TableCell><TableCell>{handle.category}</TableCell><TableCell><Input type="number" min={1} max={100} className="h-8 w-20" value={handle.posts_per_refresh} onChange={event => onUpdate(handle, { posts_per_refresh: Number(event.target.value) })}/></TableCell><TableCell><Select className="h-8 min-w-28" value={handle.refresh_frequency} onChange={event => onUpdate(handle, { refresh_frequency: event.target.value })}>{["Off", "Daily", "Every 3 days", "Weekly"].map(value => <option key={value}>{value}</option>)}</Select></TableCell><TableCell className="text-xs">{dateOrNever(handle.last_success_at)}{handle.last_error && <p className="mt-1 max-w-48 text-red-700">{handle.last_error}</p>}</TableCell><TableCell><label className="flex items-center gap-2 text-xs font-semibold"><input type="checkbox" checked={handle.enabled} onChange={event => onUpdate(handle, { enabled: event.target.checked })} className="size-4 accent-black"/>{handle.enabled ? "Enabled" : "Paused"}</label></TableCell><TableCell><div className="flex justify-end gap-1"><Button variant="ghost" size="sm" onClick={() => onRefresh([handle.id])} disabled={!handle.enabled}><RefreshCw className="size-4"/><span className="sr-only">Refresh @{handle.username}</span></Button><Button variant="ghost" size="sm" onClick={() => onDelete(handle)}><Trash2 className="size-4"/><span className="sr-only">Remove @{handle.username}</span></Button></div></TableCell></TableRow>)}</TableBody></Table>}</CardContent></Card>;
}

function LiveWork({ run, events, onCancel }: { run?: AgentRun; events: AgentEvent[]; onCancel: () => void }) {
  if (!run) return <Card><CardContent><Empty icon={Play} title="No active provider work" text="Run a confirmed handle refresh to see honest backend events here. No simulated progress is shown."/></CardContent></Card>;
  const runAgent = run.agent ?? "social-intelligence";
  return <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px]"><Card><CardHeader className="flex-row items-start justify-between"><div className="flex items-center gap-3"><AgentAvatar agentId={runAgent} size="sm" showStatus status={run.status === "Running" ? "working" : "online"}/><div><CardTitle>Live work</CardTitle><p className="mt-1 font-mono text-xs text-muted">{run.id}</p></div></div><RunBadge status={run.status}/></CardHeader><CardContent><div className="space-y-1 border-l border-line pl-5">{events.length === 0 ? <p className="py-5 text-sm text-muted">Waiting for the first persisted backend event…</p> : events.map(event => <div key={event.id} className="relative flex gap-3 py-3"><span className={`absolute -left-[24.5px] top-5 size-2 rounded-full ${event.level === "warning" ? "bg-amber-500" : "bg-[#61718b]"}`}/><AgentAvatar agentId={runAgent} size="xs"/><div><p className="text-xs font-bold uppercase tracking-wide text-muted">{event.kind.replaceAll("-", " ")} · {formatTime(event.timestamp)}</p><p className="mt-1 text-sm leading-6">{event.message}</p></div></div>)}</div></CardContent></Card><Card className="h-fit shadow-none"><CardHeader><CardTitle>Run controls</CardTitle></CardHeader><CardContent className="space-y-3"><Stat label="Status" value={run.status}/><Stat label="Started" value={dateOrNever(run.created_at)}/>{run.status === "Running" && <Button variant="outline" className="w-full" onClick={onCancel}><Pause className="size-4"/>Cancel safely</Button>}<p className="text-xs leading-5 text-muted">Partial records are preserved if a run stops, times out, reaches a budget boundary, or loses its worker.</p></CardContent></Card></div>;
}

function PostsTab({ posts, allPosts, handles, filters, setFilters, onChange }: { posts: CompetitorPost[]; allPosts: CompetitorPost[]; handles: MonitoredHandle[]; filters: PostFilters; setFilters: (filters: PostFilters) => void; onChange: () => Promise<void> }) {
  const media = Array.from(new Set(allPosts.map(item => item.media_type).filter(Boolean))) as string[];
  const formats = Array.from(new Set(allPosts.map(item => String(item.creative_attributes?.format ?? "")).filter(Boolean)));
  return <Card><CardHeader className="flex-row items-start justify-between gap-4"><div><CardTitle>Public post evidence</CardTitle><p className="mt-1 text-sm leading-6 text-muted">Metrics are stored as observed snapshots. Missing fields remain unavailable; zeros remain zero.</p></div><ManualPostDialog handles={handles} onChange={onChange}/></CardHeader><CardContent className="space-y-5"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"><Select aria-label="Platform filter" value={filters.platform} onChange={event => setFilters({ ...filters, platform: event.target.value })}><option value="all">All platforms</option><option value="instagram">Instagram</option><option value="tiktok">TikTok</option></Select><Select aria-label="Handle filter" value={filters.handle} onChange={event => setFilters({ ...filters, handle: event.target.value })}><option value="all">All handles</option>{handles.map(handle => <option key={handle.id} value={handle.id}>@{handle.username}</option>)}</Select><Input aria-label="Posted on or after" type="date" value={filters.date} onChange={event => setFilters({ ...filters, date: event.target.value })}/><Select aria-label="Media filter" value={filters.media} onChange={event => setFilters({ ...filters, media: event.target.value })}><option value="all">All media</option>{media.map(value => <option key={value}>{value}</option>)}</Select><Input aria-label="Theme filter" value={filters.theme} onChange={event => setFilters({ ...filters, theme: event.target.value })} placeholder="Theme contains…"/><Select aria-label="Format filter" value={filters.format} onChange={event => setFilters({ ...filters, format: event.target.value })}><option value="all">All formats</option>{formats.map(value => <option key={value}>{value}</option>)}</Select><Select aria-label="Performance percentile filter" value={filters.percentile} onChange={event => setFilters({ ...filters, percentile: event.target.value })}><option value="all">Any percentile</option><option value="50">Top half of baseline</option><option value="75">75th percentile or higher</option><option value="90">90th percentile or higher</option></Select><Select aria-label="Classification filter" value={filters.classified} onChange={event => setFilters({ ...filters, classified: event.target.value })}><option value="all">Any classification</option><option value="yes">Classified</option><option value="no">Not classified</option></Select><Select aria-label="Metric completeness filter" value={filters.completeness} onChange={event => setFilters({ ...filters, completeness: event.target.value })}><option value="all">Any completeness</option><option value="complete">Complete metrics</option><option value="partial">Missing metrics</option></Select></div>{posts.length === 0 ? <Empty icon={BarChart3} title="No matching public posts" text="Import real CSV/JSON records or refresh configured handles. Filters never synthesize results."/> : <div className="grid gap-4 xl:grid-cols-2">{posts.map(post => { const tags = [post.creative_attributes?.format, post.creative_attributes?.theme, post.creative_attributes?.activity].filter(Boolean).map(String); return <article key={post.id} className="rounded-2xl border border-line p-5"><div className="flex items-start gap-4">{post.remote_thumbnail_url && <div role="img" aria-label="Public post thumbnail" className="size-20 shrink-0 rounded-xl bg-cover bg-center" style={{ backgroundImage: `url(${post.remote_thumbnail_url})` }}/>}<div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-muted">{post.platform} · @{post.handle.username ?? "unknown"}</p><p className="mt-1 text-xs text-muted">{post.posted_at ? dateOrNever(post.posted_at) : "Posted date unavailable"}</p></div><Badge>{post.media_type ?? "Unavailable"}</Badge></div><p className="mt-2 line-clamp-2 text-sm leading-6">{post.caption || "Caption unavailable"}</p></div></div><div className="mt-4 grid grid-cols-4 gap-2"><Metric label="Views" value={post.view_count}/><Metric label="Likes" value={post.like_count}/><Metric label="Comments" value={post.comment_count}/><Metric label="Shares" value={post.share_count}/></div>{tags.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{tags.map(tag => <Badge key={tag}>{tag}</Badge>)}</div>}<div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted"><span>{Math.round(post.metric_completeness.percent * 100)}% metrics known</span><span>·</span><span>{post.performance.sample_size} post baseline</span>{post.performance.percentile_rank !== null && <><span>·</span><span>{post.performance.percentile_rank}th percentile</span></>}{post.performance.multiplier !== null && <><span>·</span><strong className="text-ink">{post.performance.multiplier.toFixed(2)}× account median</strong></>}{post.velocity_message && <><span>·</span><span>{post.velocity_message}</span></>}<span>·</span><PostEvidenceDialog post={post} onChange={onChange}/>{post.post_url && <><span>·</span><a href={post.post_url} target="_blank" rel="noreferrer" className="font-semibold text-ink hover:underline">Source ↗</a></>}</div></article>; })}</div>}</CardContent></Card>;
}

function ManualPostDialog({ handles, onChange }: { handles: MonitoredHandle[]; onChange: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ handle_id: handles[0]?.id ?? "", platform_post_id: "", post_url: "", caption: "", posted_at: "", media_type: "", view_count: "", like_count: "", comment_count: "", share_count: "" });
  const selected = handles.find(item => item.id === form.handle_id) ?? handles[0];
  useEffect(() => { if (!form.handle_id && handles[0]) setForm(current => ({ ...current, handle_id: handles[0].id })); }, [form.handle_id, handles]);
  async function save() {
    if (!selected || !form.platform_post_id.trim()) return;
    const optionalMetric = (value: string) => value === "" ? null : Number(value);
    try {
      await api("/api/competitor-posts", { method: "POST", body: JSON.stringify({ handle_id: selected.id, platform: selected.platform, platform_post_id: form.platform_post_id, post_url: form.post_url || null, caption: form.caption || null, posted_at: form.posted_at || null, media_type: form.media_type || null, view_count: optionalMetric(form.view_count), like_count: optionalMetric(form.like_count), comment_count: optionalMetric(form.comment_count), share_count: optionalMetric(form.share_count) }) });
      await onChange(); setOpen(false); toast.success("Manual public snapshot saved");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Manual snapshot could not be saved"); }
  }
  return <><Button size="sm" variant="outline" onClick={() => setOpen(true)} disabled={handles.length === 0}><CirclePlus className="size-4"/>Manual post</Button><Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Add a manual public post or snapshot</DialogTitle><DialogDescription>Use the same platform post ID again to append a metric snapshot without duplicating the post. Blank metrics remain unavailable.</DialogDescription></DialogHeader><div className="space-y-4"><div className="grid gap-3 sm:grid-cols-2"><Field label="Monitored handle"><Select value={form.handle_id} onChange={event => setForm({ ...form, handle_id: event.target.value })}>{handles.map(handle => <option key={handle.id} value={handle.id}>@{handle.username} · {handle.platform}</option>)}</Select></Field><Field label="Platform post ID"><Input value={form.platform_post_id} onChange={event => setForm({ ...form, platform_post_id: event.target.value })}/></Field><Field label="Public post URL"><Input value={form.post_url} onChange={event => setForm({ ...form, post_url: event.target.value })}/></Field><Field label="Posted at"><Input type="datetime-local" value={form.posted_at} onChange={event => setForm({ ...form, posted_at: event.target.value })}/></Field></div><Field label="Caption"><Textarea value={form.caption} onChange={event => setForm({ ...form, caption: event.target.value })}/></Field><div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{(["view_count", "like_count", "comment_count", "share_count"] as const).map(key => <Field key={key} label={key.replace("_count", "s").replace("view", "View").replace("like", "Like").replace("comment", "Comment").replace("share", "Share")}><Input type="number" min={0} value={form[key]} onChange={event => setForm({ ...form, [key]: event.target.value })}/></Field>)}</div><div className="flex justify-end"><Button onClick={save} disabled={!form.platform_post_id.trim()}>Save public snapshot</Button></div></div></DialogContent></Dialog></>;
}

type Snapshot = { id: string; captured_at: string; view_count: number | null; like_count: number | null; comment_count: number | null; share_count: number | null };

function PostEvidenceDialog({ post, onChange }: { post: CompetitorPost; onChange: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [attributes, setAttributes] = useState({ format: String(post.creative_attributes?.format ?? ""), theme: String(post.creative_attributes?.theme ?? ""), activity: String(post.creative_attributes?.activity ?? ""), notes: String(post.creative_attributes?.notes ?? "") });
  async function openDialog() { setOpen(true); try { setSnapshots(await api<Snapshot[]>(`/api/competitor-posts/${post.id}/snapshots`)); } catch { setSnapshots([]); } }
  async function save() { try { await api(`/api/competitor-posts/${post.id}/classification`, { method: "PUT", body: JSON.stringify({ creative_attributes: attributes }) }); await onChange(); setOpen(false); toast.success("Manual classification saved"); } catch (error) { toast.error(error instanceof Error ? error.message : "Classification could not be saved"); } }
  return <><button type="button" onClick={openDialog} className="font-semibold text-ink hover:underline">Evidence details</button><Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Post evidence</DialogTitle><DialogDescription>Review snapshot history and correct only attributes a person can support.</DialogDescription></DialogHeader><div className="space-y-5"><div><p className="text-xs font-bold uppercase tracking-wide text-muted">Metric snapshots</p>{snapshots.length < 2 ? <p className="mt-2 rounded-xl bg-wash p-3 text-sm text-muted">More snapshots are needed to calculate velocity.</p> : <SnapshotLine snapshots={snapshots}/>}<div className="mt-2 max-h-32 overflow-auto">{snapshots.map(snapshot => <div key={snapshot.id} className="flex justify-between border-b border-line py-2 text-xs"><span>{dateOrNever(snapshot.captured_at)}</span><span>Views: {snapshot.view_count === null ? "Unavailable" : snapshot.view_count.toLocaleString()}</span></div>)}</div></div><div><p className="text-xs font-bold uppercase tracking-wide text-muted">Manual creative classification</p><div className="mt-3 grid gap-3 sm:grid-cols-3"><Field label="Format"><Input value={attributes.format} onChange={event => setAttributes({ ...attributes, format: event.target.value })}/></Field><Field label="Theme"><Input value={attributes.theme} onChange={event => setAttributes({ ...attributes, theme: event.target.value })}/></Field><Field label="Activity"><Input value={attributes.activity} onChange={event => setAttributes({ ...attributes, activity: event.target.value })}/></Field></div><Field label="Notes"><Textarea className="mt-3" value={attributes.notes} onChange={event => setAttributes({ ...attributes, notes: event.target.value })}/></Field><p className="mt-2 text-xs leading-5 text-muted">Manual corrections override model or metadata classification and remain identified as manual.</p></div><div className="flex justify-end"><Button onClick={save}><Check className="size-4"/>Save correction</Button></div></div></DialogContent></Dialog></>;
}

function SnapshotLine({ snapshots }: { snapshots: Snapshot[] }) {
  const values = snapshots.map(item => item.view_count).filter((value): value is number => value !== null);
  if (values.length < 2) return <p className="mt-2 rounded-xl bg-wash p-3 text-sm text-muted">More snapshots with public view counts are needed to calculate velocity.</p>;
  const low = Math.min(...values); const high = Math.max(...values); const spread = Math.max(1, high - low);
  const points = values.map((value, index) => `${(index / Math.max(1, values.length - 1)) * 280},${70 - ((value - low) / spread) * 60}`).join(" ");
  return <div className="mt-3 rounded-xl bg-wash p-3"><svg viewBox="0 0 280 80" role="img" aria-label="Public view-count trend across collected snapshots" className="h-20 w-full"><polyline points={points} fill="none" stroke="#61718b" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/></svg><div className="flex justify-between text-[10px] text-muted"><span>{values[0].toLocaleString()} views</span><span>{values.at(-1)?.toLocaleString()} views</span></div></div>;
}

function LearningsTab({ learnings, posts, onDecision, onAnalyze }: { learnings: CompetitorLearning[]; posts: CompetitorPost[]; onDecision: (learning: CompetitorLearning, decision: "approve" | "reject") => void; onAnalyze: () => void }) {
  return <div className="space-y-4"><div className="flex justify-end"><Button variant="outline" onClick={onAnalyze} disabled={posts.length === 0}><BarChart3 className="size-4"/>Analyze existing data</Button></div>{learnings.length === 0 ? <Card><CardContent><Empty icon={Lightbulb} title="No supported public learnings yet" text="One post can be evidence, but not a pattern. Import or collect real posts, then analyze against each handle’s baseline."/></CardContent></Card> : learnings.map(learning => <Card key={learning.id}><CardHeader className="flex-row items-start justify-between"><div><Badge className={learning.status === "Approved" ? "bg-emerald-50 text-emerald-800" : learning.status === "Rejected" ? "bg-red-50 text-red-800" : ""}>{learning.status}</Badge><CardTitle className="mt-3">{learning.pattern}</CardTitle></div><Confidence value={learning.confidence}/></CardHeader><CardContent className="grid gap-4 lg:grid-cols-2"><EvidenceBlock label="Measured fact" text={learning.measured_fact}/><EvidenceBlock label="Hypothesis" text={learning.hypothesis}/><EvidenceBlock label="Recommended use" text={learning.recommendation}/><EvidenceBlock label="Data limitation" text={learning.data_limitation}/><div className="flex flex-wrap items-center gap-2 lg:col-span-2"><span className="mr-auto text-xs text-muted">Sample: {learning.sample_size} · Evidence: {learning.evidence_post_ids.length} post{learning.evidence_post_ids.length === 1 ? "" : "s"}</span>{learning.status !== "Rejected" && <Button size="sm" variant="ghost" onClick={() => onDecision(learning, "reject")}>Reject</Button>}{learning.status !== "Approved" && <Button size="sm" onClick={() => onDecision(learning, "approve")}><Check className="size-4"/>Approve learning</Button>}</div></CardContent></Card>)}</div>;
}

function DirectionsTab({ directions, approvedLearnings, onGenerate, onOpen }: { directions: CompetitorDirection[]; approvedLearnings: number; onGenerate: () => void; onOpen: (direction: CompetitorDirection) => void }) {
  return <div className="space-y-4"><div className="flex items-center justify-between gap-4"><p className="text-sm leading-6 text-muted">Directions translate reusable principles into original DINKLY moments. They must not reproduce another creator’s scene, wording, or visual signature.</p><Button onClick={onGenerate} disabled={approvedLearnings === 0}><Sparkles className="size-4"/>Generate directions</Button></div>{directions.length === 0 ? <Card><CardContent><Empty icon={Sparkles} title="No original directions yet" text={approvedLearnings ? "Generate a direction from approved public learnings." : "Approve at least one evidence-based learning first."}/></CardContent></Card> : <div className="grid gap-5 xl:grid-cols-2">{directions.map(direction => <Card key={direction.id}><CardHeader className="flex-row items-start justify-between"><div><p className="text-xs font-bold uppercase tracking-wide text-muted">{direction.signal}</p><CardTitle className="mt-2">{direction.title_pair.left} / {direction.title_pair.right}</CardTitle></div><Confidence value={direction.confidence}/></CardHeader><CardContent className="space-y-4"><EvidenceBlock label="Reusable principle" text={direction.reusable_principle}/><div className="grid gap-3 sm:grid-cols-2"><Scene label="Left scene" text={direction.left_scene}/><Scene label="Right scene" text={direction.right_scene}/></div><div className="rounded-xl bg-red-50 p-3 text-xs leading-5 text-red-800"><strong>Must not copy:</strong> {direction.must_not_copy}</div><p className="text-sm leading-6"><strong>DINKLY interpretation:</strong> {direction.dinkly_emotional_angle}</p><div className="flex items-center justify-between"><span className="text-xs text-muted">{direction.pastel_background} · {direction.accent_color}</span><Button size="sm" onClick={() => onOpen(direction)}>Open in Prompt Builder<ArrowUpRight className="size-4"/></Button></div></CardContent></Card>)}</div>}</div>;
}

function RunsTab({ runs, onOpen }: { runs: AgentRun[]; onOpen: (run: AgentRun) => void }) {
  return <Card><CardHeader><div className="flex items-center gap-3"><AgentAvatar agentId="social-intelligence" size="sm"/><div><CardTitle>Persistent agent runs</CardTitle><p className="mt-1 text-sm text-muted">Run state survives page navigation. Interrupted local work is marked honestly on restart.</p></div></div></CardHeader><CardContent>{runs.length === 0 ? <Empty icon={Clock3} title="No runs yet" text="Confirmed provider refreshes will appear here. Manual imports do not incur provider cost."/> : <Table><TableHeader><TableRow><TableHead>Run</TableHead><TableHead>Created</TableHead><TableHead>Status</TableHead><TableHead>Summary</TableHead><TableHead></TableHead></TableRow></TableHeader><TableBody>{runs.map(run => <TableRow key={run.id}><TableCell><div className="flex items-center gap-3"><AgentAvatar agentId={run.agent ?? "social-intelligence"} size="xs"/><div><p className="font-mono text-xs">{run.id}</p><p className="mt-1 text-xs text-muted">{run.kind}</p></div></div></TableCell><TableCell className="text-xs">{dateOrNever(run.created_at)}</TableCell><TableCell><RunBadge status={run.status}/></TableCell><TableCell className="text-xs text-muted">{summaryText(run.summary)}</TableCell><TableCell className="text-right"><Button variant="ghost" size="sm" onClick={() => onOpen(run)}>Open log</Button></TableCell></TableRow>)}</TableBody></Table>}</CardContent></Card>;
}

function MiniStatus({ label, value }: { label: string; value: string }) { return <div className="rounded-2xl border border-line bg-white px-4 py-3"><p className="text-[10px] font-bold uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>; }
function Stat({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-wash p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>; }
function Metric({ label, value }: { label: string; value: number | null }) { return <div className="rounded-xl bg-wash p-2.5"><p className="text-[10px] uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-sm font-semibold">{value === null ? "Unavailable" : value.toLocaleString()}</p></div>; }
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <div className="space-y-1.5"><Label>{label}</Label>{children}</div>; }
function Scene({ label, text }: { label: string; text: string }) { return <div className="rounded-xl border border-line p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-muted">{label}</p><p className="mt-2 text-sm leading-6">{text}</p></div>; }
function EvidenceBlock({ label, text }: { label: string; text: string }) { return <div><p className="text-[10px] font-bold uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-sm leading-6">{text}</p></div>; }
function Confidence({ value }: { value: string }) { return <Badge className={value === "High" ? "bg-emerald-50 text-emerald-800" : value === "Medium" ? "bg-amber-50 text-amber-900" : ""}>{value} confidence</Badge>; }
function RunBadge({ status }: { status: string }) { const warning = ["Partial", "Budget stopped", "Rate limited", "Provider unavailable", "Completed with warnings"].includes(status); return <Badge className={status === "Completed" ? "bg-emerald-50 text-emerald-800" : warning ? "bg-amber-50 text-amber-900" : status === "Failed" ? "bg-red-50 text-red-800" : ""}>{status}</Badge>; }
function Empty({ icon: Icon, title, text, action }: { icon: typeof Eye; title: string; text: string; action?: React.ReactNode }) { return <div className="flex min-h-48 flex-col items-center justify-center px-6 text-center"><div className="rounded-2xl bg-wash p-3"><Icon className={title.startsWith("Loading") ? "size-5 animate-spin text-muted" : "size-5 text-muted"}/></div><h3 className="mt-4 text-sm font-semibold">{title}</h3><p className="mt-1 max-w-lg text-sm leading-6 text-muted">{text}</p>{action && <div className="mt-4">{action}</div>}</div>; }
function Notice({ tone, items }: { tone: "warning" | "danger"; items: string[] }) { return <div className={`flex gap-2 rounded-xl p-3 text-xs leading-5 ${tone === "danger" ? "bg-red-50 text-red-900" : "bg-amber-50 text-amber-900"}`}><AlertTriangle className="mt-0.5 size-4 shrink-0"/><ul>{items.map(item => <li key={item}>• {item}</li>)}</ul></div>; }
function dateOrNever(value: string | null | undefined) { return value ? new Date(value).toLocaleString() : "Never"; }
function formatTime(value: string) { return new Date(value).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" }); }
function moneyOrUnavailable(value: number | undefined) { return value === undefined ? "Unavailable" : `$${value.toFixed(2)}`; }
function costRange(value: ProviderPreflight) { return value.estimated_cost_low === null || value.estimated_cost_high === null ? "Unknown" : `$${value.estimated_cost_low.toFixed(2)}–$${value.estimated_cost_high.toFixed(2)}`; }
function summaryText(summary: Record<string, unknown>) { const posts = summary.posts_fetched; const handles = summary.handles_processed; return posts === undefined && handles === undefined ? "No completed summary" : `${handles ?? 0} handles · ${posts ?? 0} new posts`; }
