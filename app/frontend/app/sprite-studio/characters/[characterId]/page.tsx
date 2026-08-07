"use client";

import Link from "next/link";
import { ArrowLeft, LockKeyhole } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ErrorState } from "@/components/error-state";
import { LoadingState } from "@/components/loading-state";
import { PageHeader } from "@/components/page-header";
import { SpriteLibrary } from "@/components/sprite-studio/sprite-library";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { SpriteCharacter } from "@/lib/types";

export default function SpriteCharacterPage() {
  const { characterId } = useParams<{ characterId: string }>();
  const [character, setCharacter] = useState<SpriteCharacter>();
  const [error, setError] = useState("");
  useEffect(() => { api<SpriteCharacter>(`/api/sprite-characters/${characterId}`).then(setCharacter).catch((reason: Error) => setError(reason.message)); }, [characterId]);
  if (error) return <ErrorState message={error}/>;
  if (!character) return <LoadingState cards={5}/>;
  return <div className="space-y-7"><PageHeader eyebrow="Locked model" title={character.name} description={character.notes} actions={<Button asChild variant="ghost"><Link href="/sprite-studio"><ArrowLeft className="size-4"/>Sprite Studio</Link></Button>}/><Card><CardContent className="grid gap-5 p-5 sm:grid-cols-[1fr_auto]"><div><div className="flex items-center gap-2"><LockKeyhole className="size-4"/><strong>Official references</strong><Badge>{character.reference_status}</Badge></div><ul className="mt-3 space-y-1 text-xs text-muted">{character.official_reference_paths.map(path => <li key={path}>{path}</li>)}</ul><p className="mt-3 text-xs leading-5">Only uniform scale is allowed. Bottom-center anchoring keeps nub feet attached to the floor line.</p></div><div className="grid grid-cols-2 gap-3 text-xs"><Metric label="Canvas" value={`${character.default_canvas_width}×${character.default_canvas_height}`}/><Metric label="Frame rate" value={`${character.default_frame_rate} fps`}/><Metric label="Anchor" value={`${character.default_anchor_x}, ${character.default_anchor_y}`}/><Metric label="Motions" value={String(character.animation_count ?? 0)}/></div></CardContent></Card><SpriteLibrary animations={character.animations ?? []} characters={[character]}/></div>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-wash p-3"><span className="text-muted">{label}</span><strong className="mt-1 block">{value}</strong></div>; }

