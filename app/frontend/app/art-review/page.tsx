"use client";

import { RotateCcw, ScanSearch, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { ImageDropzone } from "@/components/image-dropzone";
import { PageHeader } from "@/components/page-header";
import { PromptPreview } from "@/components/prompt-preview";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, getConcepts } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Concept } from "@/lib/types";

interface ReviewResult { recommendation: string; regenerate: boolean; reason: string; edit_prompt: string }
const groups: Record<string, string[]> = { "Character accuracy": ["Three hair tufts", "Characters different sizes", "Missing bow", "Wrong ponytail"], Anatomy: ["Long legs", "Floating"], "Eyes & face": ["Wrong eyes"], "Furniture placement": ["Standing on furniture", "Sitting on table", "Inside cart"], "Prop scale": ["Oversized prop"], Background: ["Busy background", "White background", "Realistic environment"], Color: ["Wrong background color"], Text: ["Text error"], "Brand accuracy": ["Product distorted"] };
const spriteGroups: Record<string, string[]> = { "Character accuracy": ["Wrong character", "Body proportions changed", "Wrong eyes", "Wrong orange spots", "Wrong outline thickness", "Wrong hair", "Missing bow", "Wrong ponytail"], Anatomy: ["Long arms", "Visible legs", "Human hands", "Feet detached"], "Frame consistency": ["Scale changes between frames", "Anchor jump", "Feet drift", "Cropped body"], Motion: ["Motion is not smooth", "Excessive bounce", "Independent stretch", "Loop seam is visible"], Transparency: ["Background artifact", "Frame is not transparent"] };

export default function ArtReviewPage() {
  const [file, setFile] = useState<File | null>(null);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [targetConcept, setTargetConcept] = useState("");
  const [originalPrompt, setOriginalPrompt] = useState("");
  const [failures, setFailures] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [attempts, setAttempts] = useState(0);
  const [reviewMode, setReviewMode] = useState<"comic" | "sprite">("comic");
  const [spriteFrameReference, setSpriteFrameReference] = useState("");
  const [spriteAnimationId, setSpriteAnimationId] = useState("");
  const [result, setResult] = useState<ReviewResult>();
  useEffect(() => { getConcepts().then(records => setConcepts(Array.isArray(records) ? records : [])).catch(() => setConcepts([])); const params = new URLSearchParams(window.location.search); if (params.get("mode") === "sprite") setReviewMode("sprite"); setSpriteAnimationId(params.get("animation") ?? ""); }, []);
  function toggle(failure: string) { setFailures(items => items.includes(failure) ? items.filter(item => item !== failure) : [...items, failure]); }
  async function review(forceRegeneration = false) {
    if (!failures.length) { toast.error("Select at least one visible failure"); return; }
    try { let image_path: string | null = null; if (file) { const form = new FormData(); form.append("file", file); const uploaded = await api<{ path: string }>("/api/social-posts/upload", { method: "POST", body: form }); image_path = uploaded.path; } const spriteContext = reviewMode === "sprite" ? [`Sprite animation: ${spriteAnimationId || "not linked"}`, `Issue frame: ${spriteFrameReference || "not specified"}`, "Review scale consistency, anchor consistency, motion smoothness, character accuracy, and transparency."].join("\n") : ""; const response = await api<{ review: ReviewResult }>("/api/art-reviews", { method: "POST", body: JSON.stringify({ image_path, original_prompt: originalPrompt || null, target_concept_id: targetConcept || null, failures, notes: [spriteContext, notes].filter(Boolean).join("\n\n") || null, edit_attempts: forceRegeneration ? 2 : attempts }) }); setResult(response.review); toast.success(reviewMode === "sprite" ? "Sprite review plan created" : "Review plan created"); }
    catch (error) { toast.error(error instanceof Error ? error.message : "Could not create review"); }
  }
  const activeGroups = reviewMode === "sprite" ? spriteGroups : groups;
  return <div className="space-y-7"><PageHeader eyebrow="Review" title={reviewMode === "sprite" ? "Sprite Review" : "Art QA"} description={reviewMode === "sprite" ? "Review the exact problem frame and the full loop without weakening the official character lock." : "Name the highest-priority off-model errors, repair only what is local, and regenerate when the composition is structurally unreliable."}/><div className="inline-flex rounded-xl border border-line bg-white p-1"><button type="button" onClick={() => { setReviewMode("comic"); setFailures([]); }} className={cn("rounded-lg px-4 py-2 text-xs font-semibold", reviewMode === "comic" && "bg-ink text-white")}>Comic review</button><button type="button" onClick={() => { setReviewMode("sprite"); setFailures([]); }} className={cn("rounded-lg px-4 py-2 text-xs font-semibold", reviewMode === "sprite" && "bg-ink text-white")}>Sprite review</button></div><div className="grid gap-6 xl:grid-cols-[1fr_.95fr]"><div className="space-y-5"><Card><CardHeader><CardTitle>{reviewMode === "sprite" ? "Sprite frame or loop capture" : "Generated artwork"}</CardTitle></CardHeader><CardContent className="space-y-4"><ImageDropzone onFile={setFile}/>{reviewMode === "sprite" ? <div className="grid gap-4 sm:grid-cols-2"><Field label="Animation ID"><Input value={spriteAnimationId} onChange={event => setSpriteAnimationId(event.target.value)} placeholder="sprite-animation-dinko-blink"/></Field><Field label="Problem frame"><Input value={spriteFrameReference} onChange={event => setSpriteFrameReference(event.target.value)} placeholder="Frame 3 or loop seam"/></Field></div> : <div className="grid gap-4 sm:grid-cols-2"><Field label="Target concept"><Select value={targetConcept} onChange={event => setTargetConcept(event.target.value)}><option value="">Not linked</option>{concepts.map(concept => <option key={concept.id} value={concept.id}>{concept.title_pair.left} / {concept.title_pair.right}</option>)}</Select></Field><Field label="Prior edit attempts"><Select value={attempts} onChange={event => setAttempts(Number(event.target.value))}><option value={0}>None</option><option value={1}>One</option><option value={2}>Two or more</option></Select></Field></div>}<Field label="Optional original prompt"><Textarea value={originalPrompt} onChange={event => setOriginalPrompt(event.target.value)} placeholder="Paste the generation prompt for comparison…"/></Field></CardContent></Card><Card><CardHeader><CardTitle>Manual QA checklist</CardTitle></CardHeader><CardContent className="space-y-5"><div data-testid="failure-selection" className="space-y-4">{Object.entries(activeGroups).map(([group, items]) => <fieldset key={group}><legend className="mb-2 text-[10px] font-bold uppercase tracking-[.14em] text-muted">{group}</legend><div className="flex flex-wrap gap-2">{items.map(failure => <button type="button" key={failure} onClick={() => toggle(failure)} className={cn("rounded-full border px-3 py-2 text-xs font-semibold transition", failures.includes(failure) ? "border-ink bg-ink text-white" : "border-line bg-white hover:bg-wash")}>{failure}</button>)}</div></fieldset>)}</div><Field label="Exact review notes"><Textarea value={notes} onChange={event => setNotes(event.target.value)} placeholder="Name the frame, exact area, visible issue, and what must remain unchanged."/></Field><div className="flex flex-wrap gap-2"><Button onClick={() => review()}><ScanSearch className="size-4"/>{reviewMode === "sprite" ? "Create sprite edit plan" : "Create edit prompt"}</Button><Button variant="outline" onClick={() => review(true)}><RotateCcw className="size-4"/>Recommend regeneration</Button></div></CardContent></Card></div><div>{result ? <div className="space-y-4"><Card className={result.regenerate ? "border-orange-200 bg-orange-50" : "border-emerald-200 bg-emerald-50"}><CardContent className="flex gap-4 p-5">{result.regenerate ? <RotateCcw className="size-5 text-orange-700"/> : <Wrench className="size-5 text-emerald-700"/>}<div><p className="font-semibold capitalize">{result.recommendation}</p><p className="mt-1 text-sm leading-6 text-muted">{result.reason}</p></div></CardContent></Card><PromptPreview prompt={result.edit_prompt}/></div> : <Card><CardContent className="p-6 text-sm leading-6 text-muted">{reviewMode === "sprite" ? "The frame-specific issue and loop-level consistency recommendation will appear here." : "Your targeted edit prompt—or an honest regeneration recommendation—will appear here. Identity failures and multiple structural failures are treated as regeneration risks."}</CardContent></Card>}</div></div></div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <div className="space-y-1.5"><Label>{label}</Label>{children}</div>; }
