"use client";

import Link from "next/link";
import { ArrowLeft, Film, Layers3, Sparkles } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { api, getSpriteAnimation, getSpriteAnimations } from "@/lib/api";
import type { SpriteAnimation, SpriteLayer } from "@/lib/types";

type MotionMode = "flat" | "sprite" | "mix";
interface RenderHandoff { status: string; manifest_path: string; manifest_url: string; warnings: string[]; message: string }

export default function MotionStudioPage() {
  return <Suspense fallback={<div className="p-8 text-sm text-muted">Loading Motion Studio…</div>}><MotionStudio/></Suspense>;
}

function MotionStudio() {
  const search = useSearchParams();
  const source = search.get("source");
  const animationId = search.get("animation");
  const compositionId = search.get("composition");
  const [mode, setMode] = useState<MotionMode>(source ? "sprite" : "flat");
  const [approved, setApproved] = useState<SpriteAnimation[]>([]);
  const [preloaded, setPreloaded] = useState<SpriteAnimation>();
  const [characterAnimation, setCharacterAnimation] = useState("");
  const [effectAnimation, setEffectAnimation] = useState("");
  const [handoff, setHandoff] = useState<RenderHandoff>();

  useEffect(() => {
    getSpriteAnimations("?approved=true&include_drafts=false").then(setApproved).catch(() => toast.error("Could not load approved sprite assets"));
  }, []);
  useEffect(() => {
    if (!animationId) return;
    getSpriteAnimation(animationId).then(record => {
      setPreloaded(record);
      if (record.approved) setCharacterAnimation(record.id);
    }).catch(() => toast.error("The preloaded sprite animation is unavailable"));
  }, [animationId]);

  const characterMotions = useMemo(() => approved.filter(item => ["dinko", "dinka", "shared"].includes(item.character?.character_type ?? "")), [approved]);
  const effects = useMemo(() => approved.filter(item => ["effect", "prop"].includes(item.character?.character_type ?? "")), [approved]);

  async function prepareRenderHandoff() {
    try {
      if (compositionId) {
        const result = await api<RenderHandoff>(`/api/sprite-compositions/${compositionId}/render`, { method: "POST", body: "{}" });
        setHandoff(result);
        toast.success("Remotion handoff prepared");
        return;
      }
      const chosen = approved.filter(item => [characterAnimation, effectAnimation].includes(item.id));
      if (!chosen.length) return toast.error("Select at least one approved sprite animation");
      const layers: SpriteLayer[] = chosen.map((item, index) => {
        const characterType = item.character?.character_type ?? "effect";
        const layerType = ["dinko", "dinka", "shared", "prop", "effect"].includes(characterType) ? characterType as SpriteLayer["layer_type"] : "effect";
        return { id: `motion-layer-${index + 1}`, layer_type: layerType, animation_id: item.id, label: item.name, x: 0.5, y: 1, scale: 1, start_offset_ms: 0, z_index: index + 1, visible: true, settings: {} };
      });
      const created = await api<{ composition: { id: string } }>("/api/sprite-compositions", { method: "POST", body: JSON.stringify({ name: `Motion handoff · ${chosen.map(item => item.name).join(" + ")}`, preset: null, canvas_width: 1080, canvas_height: 1080, background_color: "warm cream", loop_duration_ms: 3000, layers, notes: "Created from Motion Studio using approved sprite assets only." }) });
      const result = await api<RenderHandoff>(`/api/sprite-compositions/${created.composition.id}/render`, { method: "POST", body: "{}" });
      setHandoff(result);
      toast.success("Remotion handoff prepared");
    } catch (reason) {
      toast.error(reason instanceof Error ? reason.message : "Could not prepare motion handoff");
    }
  }

  return <div className="space-y-7"><PageHeader eyebrow="Motion handoff" title="Motion Studio" description="Choose flat comic motion, approved sprite assets, or a controlled mix before composing the final Remotion video." actions={<Button asChild variant="ghost"><Link href="/sprite-studio"><ArrowLeft className="size-4"/>Sprite Studio</Link></Button>}/>{source && <div className="rounded-2xl border border-mustard/50 bg-mustard/15 p-5"><div className="flex flex-wrap items-center gap-2"><Badge>Preloaded from Sprite Studio</Badge><strong className="text-sm">{preloaded?.name ?? (compositionId ? `Composition ${compositionId}` : `Animation ${animationId}`)}</strong>{preloaded && <Badge>{preloaded.approval_level}</Badge>}</div><p className="mt-2 text-xs text-muted">The selected record is preserved in the handoff. Only approved frames are eligible for a production manifest.</p>{preloaded && !preloaded.approved && <p className="mt-2 text-xs font-semibold text-orange-800">Finish frame and animation review before using this motion in production.</p>}</div>}<div className="grid gap-4 md:grid-cols-3"><Mode icon={Film} title="Use flat comic animation" copy="Animate an approved comic with gentle camera, text, or environment motion." active={mode === "flat"} onSelect={() => setMode("flat")}/><Mode icon={Layers3} title="Use Sprite Library" copy="Select approved character motion and approved environmental effects." active={mode === "sprite"} onSelect={() => setMode("sprite")}/><Mode icon={Sparkles} title="Mix flat comic and sprites" copy="Keep the approved comic as the base and layer selected sprite effects." active={mode === "mix"} onSelect={() => setMode("mix")}/></div>{mode !== "flat" && <Card><CardContent className="p-6"><h2 className="font-semibold">Approved Sprite Library</h2><p className="mt-2 text-sm leading-6 text-muted">Draft and technical sample animations are excluded. Finish review in Sprite Studio before they appear here.</p><div className="mt-5 grid gap-3 md:grid-cols-2"><Select aria-label="Approved character animation" value={characterAnimation} onChange={event => setCharacterAnimation(event.target.value)}><option value="">Select approved character motion</option>{characterMotions.map(item => <option key={item.id} value={item.id}>{item.character?.name} · {item.name}</option>)}</Select><Select aria-label="Approved effect animation" value={effectAnimation} onChange={event => setEffectAnimation(event.target.value)}><option value="">Optional approved prop or effect</option>{effects.map(item => <option key={item.id} value={item.id}>{item.character?.name} · {item.name}</option>)}</Select></div>{!approved.length && <p className="mt-4 rounded-xl bg-wash p-4 text-sm text-muted">Finish frame review to make animations available across the studio.</p>}<div className="mt-5 flex flex-wrap gap-2"><Button type="button" onClick={prepareRenderHandoff} disabled={!compositionId && !characterAnimation && !effectAnimation}><Film className="size-4"/>Prepare Remotion handoff</Button><Button asChild variant="outline"><Link href="/sprite-studio/composer">Open Sprite Composer</Link></Button></div>{handoff && <div className="mt-5 rounded-xl border border-line bg-wash p-4 text-sm"><div className="flex items-center gap-2"><Badge>{handoff.status.replaceAll("_", " ")}</Badge><strong>Manifest ready</strong></div><p className="mt-2 text-xs text-muted">{handoff.manifest_path}</p>{handoff.warnings.length > 0 && <ul className="mt-2 text-xs text-orange-800">{handoff.warnings.map(item => <li key={item}>• {item}</li>)}</ul>}<p className="mt-2 text-xs text-muted">{handoff.message}</p></div>}</CardContent></Card>}<Card><CardContent className="p-6"><h2 className="font-semibold">Render readiness</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-muted">Sprite Studio creates a Remotion-ready manifest with frame paths, timing, anchors, placement, and layer order. MP4 rendering activates when the optional Remotion runtime is installed; no generative video is used.</p><div className="mt-5 flex gap-2"><Button asChild><Link href="/sprite-studio/composer">Open Sprite Composer</Link></Button><Button asChild variant="outline"><Link href="/sprite-studio/exports">Review production assets</Link></Button></div></CardContent></Card></div>;
}

function Mode({ icon: Icon, title, copy, active, onSelect }: { icon: typeof Film; title: string; copy: string; active: boolean; onSelect: () => void }) {
  return <Card className={active ? "border-ink ring-2 ring-mustard" : ""}><CardContent className="p-5"><Icon className="size-5"/><h2 className="mt-4 font-semibold">{title}</h2><p className="mt-2 text-sm leading-6 text-muted">{copy}</p><Button type="button" variant={active ? "default" : "outline"} size="sm" className="mt-4" onClick={onSelect}>{active ? "Selected workflow" : "Choose workflow"}</Button></CardContent></Card>;
}
