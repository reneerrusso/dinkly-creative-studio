"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { CharacterSelector } from "@/components/sprite-studio/character-selector";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, getSpriteCharacters } from "@/lib/api";
import { spriteAnimationSchema, type SpriteAnimationFormValues } from "@/lib/schemas";
import type { SpriteAnimation, SpriteCharacter } from "@/lib/types";

export default function NewSpriteAnimationPage() {
  const router = useRouter();
  const [characters, setCharacters] = useState<SpriteCharacter[]>([]);
  const { register, handleSubmit, setValue, watch, formState: { errors, isSubmitting } } = useForm<SpriteAnimationFormValues>({ resolver: zodResolver(spriteAnimationSchema), defaultValues: { characterId: "sprite-character-dinko", name: "", category: "idle", description: "", frameRate: 8, loopMode: "loop", expectedFrameCount: 4, defaultAnchorX: 0.5, defaultAnchorY: 1, tags: "", notes: "" } });
  useEffect(() => { getSpriteCharacters().then(setCharacters).catch(() => setCharacters([])); }, []);
  async function submit(values: SpriteAnimationFormValues) { try { const response = await api<{ animation: SpriteAnimation }>("/api/sprite-animations", { method: "POST", body: JSON.stringify({ character_id: values.characterId, name: values.name, category: values.category, description: values.description, frame_rate: values.frameRate, loop: values.loopMode === "loop" || values.loopMode === "ping_pong", loop_mode: values.loopMode, expected_frame_count: values.expectedFrameCount, default_anchor_x: values.defaultAnchorX, default_anchor_y: values.defaultAnchorY, tags: values.tags.split(",").map(item => item.trim()).filter(Boolean), notes: values.notes }) }); toast.success("Animation created — add approved frames next"); router.push(`/sprite-studio/animations/${response.animation.id}?upload=1`); } catch (error) { toast.error(error instanceof Error ? error.message : "Could not create animation"); } }
  const selected = characters.find(item => item.id === watch("characterId"));
  return <div className="space-y-7"><PageHeader eyebrow="Sprite Studio" title="Create animation" description="Define one readable action, then upload approved frame artwork. The studio never invents character frames." actions={<Button asChild variant="ghost"><Link href="/sprite-studio"><ArrowLeft className="size-4"/>Library</Link></Button>}/><form onSubmit={handleSubmit(submit)} className="mx-auto max-w-5xl space-y-5"><Card><CardHeader><CardTitle>Character or asset group</CardTitle></CardHeader><CardContent className="space-y-4"><CharacterSelector characters={characters} value={watch("characterId")} onChange={value => setValue("characterId", value, { shouldValidate: true })}/>{errors.characterId && <p className="text-xs text-red-700">{errors.characterId.message}</p>}{selected?.locked && <div className="flex gap-3 rounded-xl bg-mustard/15 p-4 text-xs leading-5"><ShieldCheck className="size-4 shrink-0"/><p><strong>{selected.name} is locked.</strong> Official references, proportions, colors, spots, outline, hair, bow, ponytail, and anatomy cannot be reinterpreted by this workflow.</p></div>}</CardContent></Card><Card><CardHeader><CardTitle>Animation definition</CardTitle></CardHeader><CardContent className="space-y-4"><div className="grid gap-4 sm:grid-cols-2"><Field label="Animation name" error={errors.name?.message}><Input {...register("name")} placeholder="Blink"/></Field><Field label="Category"><Select {...register("category")}><option value="idle">Idle</option><option value="facial">Facial</option><option value="movement">Movement</option><option value="emotion">Emotion</option><option value="interaction">Interaction</option><option value="prop_action">Prop action</option><option value="sleep">Sleep</option><option value="celebration">Celebration</option><option value="shared">Shared</option><option value="environmental">Environmental</option></Select></Field></div><Field label="Description"><Textarea {...register("description")} placeholder="One subtle action with a clear beginning and end."/></Field><div className="grid gap-4 sm:grid-cols-4"><Field label="Frame rate"><Input type="number" {...register("frameRate")}/></Field><Field label="Loop mode"><Select {...register("loopMode")}><option value="loop">Loop</option><option value="ping_pong">Ping pong</option><option value="play_once">Play once</option><option value="hold_last">Hold last</option></Select></Field><Field label="Expected frames"><Input type="number" {...register("expectedFrameCount")}/></Field><Field label="Default anchor"><Input value="Bottom center · 0.5, 1" readOnly/></Field></div><div className="grid gap-4 sm:grid-cols-2"><Field label="Tags, comma separated"><Input {...register("tags")} placeholder="blink, facial, subtle"/></Field><Field label="Notes"><Input {...register("notes")} placeholder="Reviewer or illustrator notes"/></Field></div><p className="text-xs leading-5 text-muted">Fewer frames are usually better. Keep the body rigid, use uniform scale only, and let holds create charm.</p></CardContent></Card><div className="flex justify-end"><Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Creating…" : "Create and upload frames"}<ArrowRight className="size-4"/></Button></div></form></div>;
}

function Field({ label, children, error }: { label: string; children: React.ReactNode; error?: string }) { return <div className="space-y-1.5"><Label>{label}</Label>{children}{error && <p className="text-xs text-red-700">{error}</p>}</div>; }

