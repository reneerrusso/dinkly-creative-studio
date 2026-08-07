"use client";

import Image from "next/image";
import { Check, ChevronRight, GitCompareArrows, Loader2, RotateCcw, ShieldCheck, Sparkles, Wrench } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { GenerationDownloadActions } from "@/components/generation-download-actions";
import { GenerationProgress } from "@/components/generation-progress";
import { ImageModelSelector } from "@/components/image-model-selector";
import { ModelPowerBadge } from "@/components/model-power-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { API_URL, api } from "@/lib/api";
import type { GenerationCandidate, GenerationEvent, GenerationRun, GenerationStoryBrief, ImageGenerationSettings, ImageModelInfo } from "@/lib/types";
import type { StorySeed } from "@/lib/story-seed";

const finished = new Set(["awaiting_human", "approved", "rejected", "failed"]);
const eventKinds = ["brief", "prompt", "reference", "model", "progress", "generation", "candidate", "warning", "qa", "checkpoint", "selection", "repair", "approval", "rejection", "comparison", "complete"];

export default function GeneratePage() {
  return <Suspense fallback={<div className="mx-auto max-w-7xl rounded-[28px] bg-[#f1e7cf] p-7 text-sm text-muted">Preparing the DINKLY Generation Engine…</div>}><GeneratePageContent /></Suspense>;
}

function GeneratePageContent() {
  const search = useSearchParams();
  const [stories, setStories] = useState<StorySeed[]>([]);
  const [storiesLoading, setStoriesLoading] = useState(true);
  const [storiesError, setStoriesError] = useState("");
  const [storyId, setStoryId] = useState("");
  const [concept, setConcept] = useState("COFFEE. / COFFEE WITH YOU.");
  const [brief, setBrief] = useState<GenerationStoryBrief>();
  const [run, setRun] = useState<GenerationRun>();
  const [events, setEvents] = useState<GenerationEvent[]>([]);
  const [models, setModels] = useState<ImageModelInfo[]>([]);
  const [busy, setBusy] = useState(false);
  const [buildingStory, setBuildingStory] = useState(false);
  const [error, setError] = useState("");
  const [modelMode, setModelMode] = useState<"automatic" | "lite" | "balanced" | "pro">("automatic");
  const [candidateCount, setCandidateCount] = useState(4);
  const [confirmPro, setConfirmPro] = useState(false);
  const [includeProCompare, setIncludeProCompare] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const sourceRef = useRef<EventSource | undefined>(undefined);
  const loadedStoryRef = useRef<string | undefined>(undefined);
  const storyRetryRef = useRef<number | undefined>(undefined);
  const briefRef = useRef<HTMLDivElement | null>(null);

  const refreshRun = useCallback(async (runId: string) => {
    const latest = await api<GenerationRun>(`/api/generation-engine/runs/${runId}`);
    setRun(latest);
    if (finished.has(latest.status) && pollRef.current) clearInterval(pollRef.current);
    return latest;
  }, []);

  const watchRun = useCallback((runId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    sourceRef.current?.close();
    pollRef.current = setInterval(() => { refreshRun(runId).catch(() => undefined); }, 1200);
    const source = new EventSource(`${API_URL}/api/generation-engine/runs/${runId}/stream`);
    sourceRef.current = source;
    eventKinds.forEach(kind => source.addEventListener(kind, event => {
      const payload = JSON.parse((event as MessageEvent).data) as GenerationEvent;
      setEvents(current => current.some(item => item.id === payload.id) ? current : [...current, payload]);
    }));
    source.onerror = () => source.close();
  }, [refreshRun]);

  const loadStories = useCallback(async () => {
    if (storyRetryRef.current) window.clearTimeout(storyRetryRef.current);
    storyRetryRef.current = undefined;
    setStoriesLoading(true);
    try {
      const result = await api<StorySeed[]>("/api/story-library", { timeoutMs: 8_000 });
      if (!result.length) throw new Error("The Story Library returned no stories.");
      setStories(result);
      setStoriesError("");
      return true;
    } catch (caught) {
      setStoriesError(caught instanceof Error ? caught.message : "Could not load the Story Library.");
      return false;
    } finally {
      setStoriesLoading(false);
    }
  }, []);

  const buildStory = useCallback(async (overrideStoryId?: string) => {
    const selectedStoryId = overrideStoryId || storyId;
    const conceptText = concept.trim();
    if (!selectedStoryId && !conceptText) {
      setError("Enter a simple concept or choose a Story Library story first.");
      return;
    }
    setBuildingStory(true); setError(""); setRun(undefined); setEvents([]); window.localStorage.removeItem("dinkly-active-generation-run");
    try {
      const payload = selectedStoryId ? { story_id: selectedStoryId } : { concept_text: conceptText };
      const result = await api<{ story_brief: GenerationStoryBrief }>("/api/generation-engine/brief", { method: "POST", body: JSON.stringify(payload), timeoutMs: 10_000 });
      setBrief(result.story_brief);
      toast.success("Story brief built");
      window.requestAnimationFrame(() => briefRef.current?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }));
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Could not build story";
      setError(message === "Failed to fetch" ? "The Generation Engine API is not reachable. Keep pnpm dev running, then try again." : message);
    } finally { setBuildingStory(false); }
  }, [concept, storyId]);

  useEffect(() => {
    let stopped = false;
    let storyLoadAttempt = 0;
    const loadStoryLibrary = async () => {
      const loaded = await loadStories();
      if (!loaded && !stopped && storyLoadAttempt < 3) {
        storyLoadAttempt += 1;
        storyRetryRef.current = window.setTimeout(() => { void loadStoryLibrary(); }, 1000 * storyLoadAttempt);
      }
    };
    void loadStoryLibrary();
    api<ImageModelInfo[]>("/api/image-models").then(setModels).catch(() => setModels([]));
    api<ImageGenerationSettings>("/api/generation-engine/settings").then(settings => {
      const remembered = window.localStorage.getItem("dinkly-image-model-selection") as typeof modelMode | null;
      setModelMode(remembered ?? settings.default_selection);
      setCandidateCount(settings.candidate_count);
    }).catch(() => undefined);
    const activeRunId = window.localStorage.getItem("dinkly-active-generation-run");
    if (activeRunId) refreshRun(activeRunId).then(latest => { setBrief(latest.story_brief); watchRun(activeRunId); }).catch(() => window.localStorage.removeItem("dinkly-active-generation-run"));
    return () => { stopped = true; if (pollRef.current) clearInterval(pollRef.current); if (storyRetryRef.current) clearTimeout(storyRetryRef.current); sourceRef.current?.close(); };
  }, [loadStories, refreshRun, watchRun]);

  useEffect(() => {
    const selected = search.get("story");
    if (selected && loadedStoryRef.current !== selected) { loadedStoryRef.current = selected; setStoryId(selected); buildStory(selected); }
  }, [buildStory, search]);

  async function generate() {
    if (!brief) return;
    setBusy(true); setError(""); setEvents([]);
    try {
      const started = await api<GenerationRun>("/api/generation-engine/generate", { method: "POST", body: JSON.stringify({ story_brief: brief, model_selection_mode: modelMode, candidate_count: candidateCount, aspect_ratio: "1:1", confirm_pro: confirmPro }) });
      setRun(started); window.localStorage.setItem("dinkly-active-generation-run", started.id); watchRun(started.id);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Generation could not start"); }
    finally { setBusy(false); }
  }

  async function compareModels() {
    if (!brief) return;
    setBusy(true); setError(""); setEvents([]);
    try {
      const maxModel = models.find(model => model.power_level === 3);
      const confirm = includeProCompare ? window.confirm(`Add one ${maxModel?.display_name ?? "MAX-tier"} candidate to this comparison? This incurs an additional estimated cost.`) : false;
      if (includeProCompare && !confirm) return;
      const started = await api<GenerationRun>("/api/generation-engine/model-compare", { method: "POST", body: JSON.stringify({ story_brief: brief, include_pro: includeProCompare, confirm_pro: confirm, aspect_ratio: "1:1" }) });
      setRun(started); window.localStorage.setItem("dinkly-active-generation-run", started.id); watchRun(started.id);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Comparison could not start"); }
    finally { setBusy(false); }
  }

  async function selectCandidate(candidate: GenerationCandidate) {
    if (!run) return;
    const updated = await api<GenerationRun>(`/api/generation-engine/candidates/${candidate.id}/select`, { method: "POST", body: JSON.stringify({ selected: true }) });
    setRun(updated);
  }

  async function repairCandidate(candidate: GenerationCandidate, modelSelection: "same" | "balanced" | "pro" = "same") {
    if (!run) return;
    const failures = candidate.qa_findings.filter(item => item.status !== "Pass").map(item => item.check);
    if (!failures.length) { toast.info("No detected QA issue needs repair"); return; }
    setBusy(true);
    try {
      const maxModel = models.find(model => model.power_level === 3);
      const confirm = modelSelection === "pro" ? window.confirm(`Use ${maxModel?.display_name ?? "the MAX tier"} for this repair? This may cost more and requires explicit approval.`) : false;
      if (modelSelection === "pro" && !confirm) return;
      const updated = await api<GenerationRun>(`/api/generation-engine/candidates/${candidate.id}/repair`, { method: "POST", body: JSON.stringify({ failures, model_selection: modelSelection, confirm_pro: confirm }) });
      setRun(updated); toast.success("Repair received and re-reviewed");
    } catch (caught) { toast.error(caught instanceof Error ? caught.message : "Repair failed"); }
    finally { setBusy(false); }
  }

  async function retryCandidate(candidate: GenerationCandidate) {
    setBusy(true);
    try {
      const isPro = candidate.model === "nano_banana_pro";
      const confirm = isPro ? window.confirm(`Retry this candidate with ${candidate.model_display_name}? This incurs an additional estimated cost.`) : false;
      if (isPro && !confirm) return;
      const updated = await api<GenerationRun>(`/api/generation-engine/candidates/${candidate.id}/retry`, { method: "POST", body: JSON.stringify({ confirm_pro: confirm }) });
      setRun(updated); toast.success(`Candidate ${candidate.label} retry received`);
    } catch (caught) { toast.error(caught instanceof Error ? caught.message : "Retry failed"); }
    finally { setBusy(false); }
  }

  async function approve() {
    if (!run) return;
    setBusy(true);
    try { const updated = await api<GenerationRun>(`/api/generation-engine/runs/${run.id}/approve`, { method: "POST", body: JSON.stringify({ approved_by: "Human reviewer" }) }); setRun(updated); toast.success("Comic approved and added to History"); }
    catch (caught) { toast.error(caught instanceof Error ? caught.message : "Approval failed"); }
    finally { setBusy(false); }
  }

  async function cancelRun() {
    if (!run) return;
    try { const updated = await api<GenerationRun>(`/api/generation-engine/runs/${run.id}/cancel`, { method: "POST" }); setRun(updated); }
    catch (caught) { toast.error(caught instanceof Error ? caught.message : "Could not cancel run"); }
  }

  const selected = useMemo(() => run?.candidates.find(item => item.id === run.selected_candidate_id) ?? run?.candidates.find(item => item.recommended), [run]);

  return <div className="mx-auto max-w-7xl space-y-7 pb-16">
    <header className="grid gap-6 rounded-[28px] border border-black/[0.06] bg-[#f1e7cf] p-7 shadow-[0_28px_80px_-65px_rgba(40,34,22,.55)] md:grid-cols-[1fr_auto] md:items-end">
      <div><p className="text-[10px] font-bold uppercase tracking-[.22em] text-[#8c6325]">DINKLY Generation Engine</p><h1 className="mt-3 text-4xl font-semibold tracking-[-.045em] sm:text-5xl">What should DINKLY make?</h1><p className="mt-3 text-sm text-[#6f675d]">Original IP. Scalable content. Human taste.</p></div>
      <div className="rounded-2xl bg-white/70 p-4 text-right"><p className="text-[10px] font-bold uppercase tracking-[.16em] text-[#8c6325]">One studio operator</p><p className="mt-1 text-xs text-muted">Live status stays visible in the agent strip above.</p></div>
    </header>

    <Card><CardContent className="space-y-5 p-6 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-muted">Story Builder</p><p className="mt-1 text-sm text-muted">Start with your own idea or develop a complete scene from the Story Library.</p></div><p className="text-xs font-semibold text-[#8c6325]" aria-live="polite">{storiesLoading ? "Loading Story Library…" : stories.length ? `${stories.length} Story Library concepts ready` : "Story Library needs attention"}</p></div>
      <div className="grid gap-4 lg:grid-cols-[1fr_auto_1fr_auto] lg:items-end"><Field label="Simple concept" htmlFor="generation-simple-concept"><Input id="generation-simple-concept" value={concept} onChange={event => { setConcept(event.target.value); setStoryId(""); }} placeholder="COFFEE. / COFFEE WITH YOU." /></Field><span className="hidden pb-3 text-xs text-muted lg:block">or</span><Field label="Choose from Story Library" htmlFor="generation-story-library"><Select id="generation-story-library" value={storyId} disabled={storiesLoading && !stories.length} onChange={event => { const nextId = event.target.value; setStoryId(nextId); const story = stories.find(item => item.id === nextId); if (story) setConcept(`${story.title_left ?? story.title} / ${story.title_right ?? "WITH YOU"}`); if (nextId) void buildStory(nextId); }}><option value="">{storiesLoading && !stories.length ? "Loading Story Library…" : stories.length ? "Choose a structured story…" : "No stories loaded — retry below"}</option>{stories.map(story => <option key={story.id} value={story.id}>{story.title_left ?? story.title} / {story.title_right ?? "WITH YOU"}</option>)}</Select></Field><Button type="button" onClick={() => void buildStory()} disabled={buildingStory || (!storyId && !concept.trim())} aria-busy={buildingStory}>{buildingStory ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}{buildingStory ? "Building…" : "Build Story"}</Button></div>
      {storiesError && <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900"><span>The Story Library could not load yet. Your simple concept still works.</span><Button type="button" size="sm" variant="outline" onClick={() => void loadStories()} disabled={storiesLoading}>{storiesLoading ? "Retrying…" : "Retry Story Library"}</Button></div>}
      {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    </CardContent></Card>

    {brief && <div ref={briefRef}><StoryBriefEditor brief={brief} onChange={setBrief} /></div>}

    {brief && <Card><CardContent className="space-y-5 p-6"><ImageModelSelector value={modelMode} models={models} selectedForRun={run?.selected_model_info} selectionReason={run?.selection_reason} onChange={value => { setModelMode(value); window.localStorage.setItem("dinkly-image-model-selection", value); }} /><div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end"><Field label="Candidates"><Select value={candidateCount} onChange={event => setCandidateCount(Number(event.target.value))}>{[1, 2, 3, 4].map(value => <option key={value} value={value}>{value}</option>)}</Select></Field><div className="flex flex-wrap gap-2"><Button variant="outline" onClick={compareModels} disabled={busy}><GitCompareArrows className="size-4" />Compare Models</Button><Button onClick={generate} disabled={busy}>{busy ? <Loader2 className="size-4 animate-pulse" /> : <Sparkles className="size-4" />}Generate</Button></div></div><label className="flex items-center gap-2 text-xs text-muted"><input type="checkbox" checked={includeProCompare} onChange={event => setIncludeProCompare(event.target.checked)} />Optionally add one {models.find(model => model.power_level === 3)?.power_label ?? "MAX"} candidate to model comparison; confirmation is required before the call.</label>{modelMode === "pro" && <label className="flex items-center gap-2 rounded-xl bg-amber-50 p-3 text-xs text-amber-900"><input type="checkbox" checked={confirmPro} onChange={event => setConfirmPro(event.target.checked)} />I approve the estimated {models.find(model => model.power_level === 3)?.power_label ?? "MAX"} cost for this run.</label>}</CardContent></Card>}

    {run && <RunWorkspace run={run} events={events} selected={selected} onSelect={selectCandidate} onRetry={retryCandidate} onRepair={repairCandidate} onApprove={approve} onCancel={cancelRun} onAnother={() => { setRun(undefined); setEvents([]); window.localStorage.removeItem("dinkly-active-generation-run"); }} onEdit={() => { setRun(undefined); window.localStorage.removeItem("dinkly-active-generation-run"); }} busy={busy} />}
  </div>;
}

function StoryBriefEditor({ brief, onChange }: { brief: GenerationStoryBrief; onChange: (value: GenerationStoryBrief) => void }) {
  const update = <K extends keyof GenerationStoryBrief>(key: K, value: GenerationStoryBrief[K]) => onChange({ ...brief, [key]: value });
  return <Card><CardContent className="space-y-6 p-6 sm:p-7"><div><p className="text-[10px] font-bold uppercase tracking-[.2em] text-muted">Story Brief</p><h2 className="mt-2 text-2xl font-semibold tracking-[-.025em]">The production story, before the prompt</h2></div><div className="grid gap-4 md:grid-cols-2"><Field label="Format"><Select value={brief.format} onChange={event => update("format", event.target.value)}><option value="x-with-you">X / X WITH YOU</option><option value="before-after">Before / After</option><option value="single-panel">Single panel</option></Select></Field><Field label="Camera angle"><Input value={brief.camera_angle} onChange={event => update("camera_angle", event.target.value)} /></Field><Field label="Left title"><Input value={brief.title_left} onChange={event => update("title_left", event.target.value)} /></Field><Field label="Right title"><Input value={brief.title_right} onChange={event => update("title_right", event.target.value)} /></Field></div><div className="grid gap-4 lg:grid-cols-2"><Panel title="Left panel"><Field label="Character"><Select value={brief.left_character} onChange={event => update("left_character", event.target.value as "boy" | "girl")}><option value="boy">Dinko</option><option value="girl">Dinka</option></Select></Field><Field label="Action"><Textarea value={brief.left_action} onChange={event => update("left_action", event.target.value)} /></Field><Field label="Setting"><Input value={brief.left_setting} onChange={event => update("left_setting", event.target.value)} /></Field><Field label="Props"><Input value={brief.left_props.join(", ")} onChange={event => update("left_props", csv(event.target.value))} /></Field><Field label="Emotion"><Input value={brief.left_emotion} onChange={event => update("left_emotion", event.target.value)} /></Field></Panel><Panel title="Right panel"><Field label="Characters"><Input value="Dinko + Dinka" disabled /></Field><Field label="Action"><Textarea value={brief.right_action} onChange={event => update("right_action", event.target.value)} /></Field><Field label="Setting"><Input value={brief.right_setting} onChange={event => update("right_setting", event.target.value)} /></Field><Field label="Props"><Input value={brief.right_props.join(", ")} onChange={event => update("right_props", csv(event.target.value))} /></Field><Field label="Emotion"><Input value={brief.right_emotion} onChange={event => update("right_emotion", event.target.value)} /></Field></Panel></div><div className="grid gap-4 md:grid-cols-2"><Field label="Shared environment"><Textarea value={brief.shared_environment} onChange={event => update("shared_environment", event.target.value)} /></Field><Field label="Environmental contrast"><Textarea value={brief.environmental_contrast} onChange={event => update("environmental_contrast", event.target.value)} /></Field><Field label="Background color"><Input value={brief.background_color} onChange={event => update("background_color", event.target.value)} /></Field><Field label="Accent color"><Input value={brief.accent_color} onChange={event => update("accent_color", event.target.value)} /></Field><Field label="Emotional insight"><Textarea value={brief.emotional_insight} onChange={event => update("emotional_insight", event.target.value)} /></Field><Field label="Execution risks"><Textarea value={brief.execution_risks.join("\n")} onChange={event => update("execution_risks", event.target.value.split("\n").filter(Boolean))} /></Field></div></CardContent></Card>;
}

function RunWorkspace({ run, events, selected, onSelect, onRetry, onRepair, onApprove, onCancel, onAnother, onEdit, busy }: { run: GenerationRun; events: GenerationEvent[]; selected?: GenerationCandidate; onSelect: (candidate: GenerationCandidate) => void; onRetry: (candidate: GenerationCandidate) => void; onRepair: (candidate: GenerationCandidate, model?: "same" | "balanced" | "pro") => void; onApprove: () => void; onCancel: () => void; onAnother: () => void; onEdit: () => void; busy: boolean }) {
  const active = !finished.has(run.status);
  return <div className="space-y-6"><GenerationProgress run={run} events={events} /><Card className="overflow-hidden"><CardContent className="grid gap-6 p-6 lg:grid-cols-[.78fr_1.22fr]"><section><div><p className="font-semibold">Live production work</p><p className="text-xs text-muted">{active ? "The DINKLY Agent strip reflects this real event stream." : statusLabel(run.status)}</p></div><div className="mt-5 max-h-48 space-y-2 overflow-y-auto border-l-2 border-mustard/45 pl-4">{(events.length ? events.slice(-10) : [{ id: "initial", message: "Story brief ready." }]).map(event => <p key={event.id} className="text-xs leading-5 text-muted">{event.message}</p>)}</div>{active && <Button className="mt-4" size="sm" variant="ghost" onClick={onCancel}>Cancel run</Button>}</section><section className="rounded-2xl bg-wash/70 p-5"><div className="flex items-center justify-between gap-3"><p className="text-xs font-bold uppercase tracking-[.16em]">Generation recipe</p><div className="flex items-center gap-2">{run.selected_model_info && <ModelPowerBadge model={run.selected_model_info} compact />}<Badge>{run.comparison ? "Model comparison" : run.model_selection_mode}</Badge></div></div>{run.generation_recipe ? <div className="mt-4 grid gap-2 sm:grid-cols-2">{run.generation_recipe.map(item => <p key={item} className="flex items-center gap-2 text-xs"><Check className="size-3.5 text-emerald-700" />{item}</p>)}</div> : <p className="mt-4 text-sm text-muted">Recipe compiled. Developer Mode can expose the raw prompt.</p>}<div className="mt-4 border-t border-line pt-4 text-xs text-muted"><p>{run.selection_reason}</p><p className="mt-1">Estimated cost: {run.estimated_cost == null ? "Unavailable" : `~$${run.estimated_cost.toFixed(4)}`} · estimates are not exact charges.</p></div>{run.prompt_record.prompt && <details className="mt-4"><summary className="cursor-pointer text-xs font-semibold">Developer prompt</summary><pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded-xl bg-white p-4 text-[11px] leading-5">{run.prompt_record.prompt}</pre></details>}</section></CardContent></Card>

    {run.candidates.length > 0 && <section><div className="mb-4 flex items-end justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[.18em] text-muted">Candidates</p><h2 className="mt-1 text-2xl font-semibold">Choose with taste, not virality</h2></div>{run.candidates.filter(item => item.image_path).length !== run.candidate_count && <span className="text-xs text-amber-800">{run.candidates.filter(item => item.image_path).length} of {run.candidate_count} generated</span>}</div><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">{run.candidates.map(candidate => <CandidateCard key={candidate.id} candidate={candidate} selected={run.selected_candidate_id === candidate.id} onSelect={() => onSelect(candidate)} onRetry={() => onRetry(candidate)} />)}</div></section>}

    {selected && <Card><CardContent className="grid gap-6 p-6 lg:grid-cols-[.85fr_1.15fr]"><div className="relative aspect-square overflow-hidden rounded-2xl bg-wash">{selected.asset_url && <Image src={`${API_URL}${selected.asset_url}`} alt={`Candidate ${selected.label}`} fill unoptimized className="object-contain" />}</div><div><div className="flex flex-wrap items-center gap-2"><h3 className="text-xl font-semibold">Candidate {selected.label}</h3><QaBadge value={selected.qa_status} />{selected.recommended && <Badge>Recommended</Badge>}<ModelPowerBadge model={{ display_name: selected.model_display_name, power_label: selected.model_power_label, power_level: selected.model_power_level }} compact /></div><p className="mt-2 text-sm text-muted">{selected.qa_summary}</p><div className="mt-5 grid gap-2">{selected.qa_findings.length ? selected.qa_findings.map((finding, index) => <div key={`${finding.check}-${index}`} className="flex gap-3 rounded-xl border border-line p-3"><span className={finding.status === "Pass" ? "text-emerald-700" : finding.status === "Warning" ? "text-amber-700" : "text-red-700"}>{finding.status === "Pass" ? "✓" : "!"}</span><div><p className="text-xs font-semibold">{finding.check}</p><p className="mt-1 text-xs leading-5 text-muted">{finding.detail}</p></div></div>) : <p className="rounded-xl bg-wash p-4 text-sm text-muted">Automated visual QA unavailable. Complete a manual review before approval.</p>}</div>{selected.qa_findings.some(item => item.status !== "Pass") && <div className="mt-5 flex flex-wrap gap-2"><Button variant="outline" onClick={() => onRepair(selected, "same")} disabled={busy}><Wrench className="size-4" />Fix Issues</Button><Button variant="ghost" onClick={() => onRepair(selected, "balanced")} disabled={busy}>Upgrade to BALANCED</Button><Button variant="ghost" onClick={() => onRepair(selected, "pro")} disabled={busy}>Upgrade to MAX</Button></div>}</div></CardContent></Card>}

    {run.status === "awaiting_human" && <section className="rounded-[28px] border border-[#b99a48]/30 bg-[#f2e7c7] p-7 text-center"><ShieldCheck className="mx-auto size-7 text-[#8b6a18]" /><p className="mt-3 text-[10px] font-bold uppercase tracking-[.2em] text-[#8b6a18]">Human checkpoint</p><h2 className="mt-2 text-3xl font-semibold tracking-[-.035em]">This is where taste enters the loop.</h2><div className="mt-6 flex flex-wrap justify-center gap-2"><Button onClick={onApprove} disabled={!run.selected_candidate_id || busy}><Check className="size-4" />Approve Comic</Button><Button variant="outline" onClick={onAnother}><RotateCcw className="size-4" />Make Another</Button><Button variant="ghost" onClick={onEdit}>Edit Story <ChevronRight className="size-4" /></Button></div></section>}
    {run.status === "approved" && <GenerationDownloadActions run={run} />}
    {run.status === "failed" && <p role="alert" className="rounded-2xl bg-red-50 p-5 text-sm text-red-800">{run.error || "Generation failed."}</p>}
  </div>;
}

function CandidateCard({ candidate, selected, onSelect, onRetry }: { candidate: GenerationCandidate; selected: boolean; onSelect: () => void; onRetry: () => void }) {
  const model = { display_name: candidate.model_display_name, power_label: candidate.model_power_label, power_level: candidate.model_power_level };
  return <Card className={selected ? "ring-2 ring-mustard" : ""}><CardContent className="p-3"><div className="relative aspect-square overflow-hidden rounded-xl bg-wash">{candidate.asset_url ? <Image src={`${API_URL}${candidate.asset_url}`} alt={`Candidate ${candidate.label}`} fill unoptimized className="object-contain" /> : <div className="flex size-full items-center justify-center p-4 text-center text-xs text-red-700">{candidate.error?.message ?? "Candidate failed"}</div>}{candidate.recommended && <Badge className="absolute left-2 top-2">Recommended</Badge>}</div><div className="mt-3 flex items-start justify-between gap-2"><div><p className="text-sm font-semibold">{candidate.label}</p><div className="mt-1"><ModelPowerBadge model={model} /></div></div><QaBadge value={candidate.qa_status} /></div>{candidate.image_path && <p className="mt-2 text-[10px] text-muted">{candidate.runtime_ms == null ? "Runtime unavailable" : `${(candidate.runtime_ms / 1000).toFixed(1)}s`} · {candidate.reported_cost != null ? `$${candidate.reported_cost.toFixed(4)} reported` : candidate.estimated_cost != null ? `~$${candidate.estimated_cost.toFixed(4)} estimated` : "Cost unavailable"}</p>}{candidate.asset_url ? <Button className="mt-3 w-full" size="sm" variant={selected ? "default" : "outline"} onClick={onSelect}>{selected ? "Selected" : "Select"}</Button> : candidate.error?.retryable ? <Button className="mt-3 w-full" size="sm" variant="outline" onClick={onRetry}>Retry Candidate</Button> : null}</CardContent></Card>;
}

function QaBadge({ value }: { value: GenerationCandidate["qa_status"] }) {
  const tone = value === "Pass" ? "bg-emerald-100 text-emerald-800" : value === "Warning" ? "bg-amber-100 text-amber-900" : value === "Fail" ? "bg-red-100 text-red-800" : "bg-neutral-100 text-neutral-700";
  return <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${tone}`}>{value}</span>;
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) { return <section className="space-y-4 rounded-2xl border border-line bg-wash/35 p-5"><p className="text-xs font-bold uppercase tracking-[.16em]">{title}</p>{children}</section>; }
function Field({ label, children, htmlFor }: { label: string; children: React.ReactNode; htmlFor?: string }) { return <div className="space-y-1.5"><Label htmlFor={htmlFor}>{label}</Label>{children}</div>; }
function csv(value: string) { return value.split(",").map(item => item.trim()).filter(Boolean).slice(0, 6); }
function statusLabel(status: GenerationRun["status"]) { return ({ awaiting_human: "Ready for your decision", approved: "Approved", rejected: "Rejected", failed: "Needs attention" } as Record<string, string>)[status] ?? status.replaceAll("_", " "); }
