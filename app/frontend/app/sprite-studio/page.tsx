"use client";

import Link from "next/link";
import { FileUp, Layers3, Plus, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { ErrorState } from "@/components/error-state";
import { LoadingState } from "@/components/loading-state";
import { PageHeader } from "@/components/page-header";
import { SpriteLibrary } from "@/components/sprite-studio/sprite-library";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getSpriteAnimations, getSpriteCharacters } from "@/lib/api";
import type { SpriteAnimation, SpriteCharacter } from "@/lib/types";

const starters = ["Blink", "Idle", "Floating hearts", "Coffee steam", "Hug"];

export default function SpriteStudioPage() {
  const [characters, setCharacters] = useState<SpriteCharacter[]>();
  const [animations, setAnimations] = useState<SpriteAnimation[]>();
  const [error, setError] = useState("");
  useEffect(() => { Promise.all([getSpriteCharacters(), getSpriteAnimations()]).then(([characterData, animationData]) => { setCharacters(characterData); setAnimations(animationData); }).catch((reason: Error) => setError(reason.message)); }, []);
  const starterAnimations = useMemo(() => (animations ?? []).filter(animation => starters.includes(animation.name)).slice(0, 7), [animations]);
  return <div className="space-y-7"><PageHeader eyebrow="Reusable motion" title="Sprite Studio" description="Create small, expressive frame-by-frame motion without regenerating or deforming Dinko and Dinka." actions={<div className="flex flex-wrap gap-2"><Button asChild><Link href="/sprite-studio/new"><Plus className="size-4"/>Create animation</Link></Button><Button asChild variant="outline"><Link href="/sprite-studio/composer"><Layers3 className="size-4"/>Open Composer</Link></Button></div>}/>{error && <ErrorState message={error}/>} {(!characters || !animations) && !error && <LoadingState cards={6}/>} {characters && animations && <><section><div className="mb-3 flex items-end justify-between"><div><h2 className="text-lg font-semibold">Locked character sources</h2><p className="mt-1 text-xs text-muted">Official references control identity. Animation frames control motion only.</p></div><Badge>Character lock active</Badge></div><div className="grid gap-4 md:grid-cols-2">{characters.filter(character => ["dinko", "dinka"].includes(character.character_type)).map(character => <Link href={`/sprite-studio/characters/${character.id}`} key={character.id}><Card className="transition hover:border-ink"><CardContent className="flex items-center justify-between p-5"><div><div className="flex items-center gap-2"><h3 className="font-semibold">{character.name}</h3><Badge>Locked</Badge></div><p className="mt-2 text-xs text-muted">{character.reference_status} · {character.animation_count} motion definitions</p></div><div className="text-right text-xs text-muted"><strong className="block text-ink">{character.default_canvas_width}×{character.default_canvas_height}</strong>bottom-center anchor</div></CardContent></Card></Link>)}</div></section><section><div className="mb-3"><h2 className="text-lg font-semibold">Start here</h2><p className="mt-1 text-xs text-muted">Definitions are ready. They remain Frames needed until approved artwork is uploaded.</p></div><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{starterAnimations.map(animation => <Link key={animation.id} href={`/sprite-studio/animations/${animation.id}`} className="rounded-xl border border-line bg-white p-4 transition hover:border-ink"><div className="flex justify-between gap-2"><span className="text-sm font-semibold">{animation.character?.name} {animation.name}</span><Badge>{animation.status}</Badge></div><p className="mt-2 text-xs text-muted">Recommended {animation.expected_frame_count} frames · {animation.loop_mode.replaceAll("_", " ")}</p></Link>)}</div></section><section className="grid gap-3 sm:grid-cols-3"><Action icon={UploadCloud} href="/sprite-studio/new?next=upload" title="Upload frames" copy="Create or choose an animation, then add transparent PNG or WEBP frames."/><Action icon={FileUp} href="/sprite-studio/new?next=sheet" title="Import sprite sheet" copy="Define a slicing grid, deselect unused cells, and preserve every existing frame."/><Action icon={Layers3} href="/sprite-studio/composer" title="Compose a scene" copy="Layer approved motions, props, and effects into a simple reusable scene."/></section><section><div className="mb-3 flex items-end justify-between"><div><h2 className="text-lg font-semibold">Motion library</h2><p className="mt-1 text-xs text-muted">Draft definitions stay visible here; only approved motion appears in production selectors.</p></div><Button asChild variant="ghost" size="sm"><Link href="/sprite-studio/exports">View exports</Link></Button></div><SpriteLibrary animations={animations} characters={characters}/></section></>}</div>;
}

function Action({ icon: Icon, href, title, copy }: { icon: typeof Layers3; href: string; title: string; copy: string }) { return <Link href={href} className="rounded-2xl border border-line bg-white p-5 transition hover:border-ink"><Icon className="size-5"/><h3 className="mt-4 text-sm font-semibold">{title}</h3><p className="mt-2 text-xs leading-5 text-muted">{copy}</p></Link>; }

