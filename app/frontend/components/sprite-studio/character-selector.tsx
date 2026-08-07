"use client";

import type { SpriteCharacter } from "@/lib/types";
import { cn } from "@/lib/utils";

export function CharacterSelector({ characters, value, onChange }: { characters: SpriteCharacter[]; value: string; onChange: (value: string) => void }) {
  return <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">{characters.map(character => <button key={character.id} type="button" onClick={() => onChange(character.id)} className={cn("rounded-xl border p-3 text-left transition", value === character.id ? "border-ink bg-mustard/25" : "border-line bg-white hover:bg-wash")}><span className="block text-sm font-semibold">{character.name}</span><span className="mt-1 block text-[11px] capitalize text-muted">{character.character_type} · {character.reference_status}</span></button>)}</div>;
}

