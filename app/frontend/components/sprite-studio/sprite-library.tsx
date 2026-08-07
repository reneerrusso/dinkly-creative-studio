"use client";

import { useMemo, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { SpriteCard } from "@/components/sprite-studio/sprite-card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { SpriteAnimation, SpriteCharacter } from "@/lib/types";
import { Film } from "lucide-react";

export function SpriteLibrary({ animations, characters }: { animations: SpriteAnimation[]; characters: SpriteCharacter[] }) {
  const [character, setCharacter] = useState("all");
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("all");
  const [availability, setAvailability] = useState("all");
  const [approval, setApproval] = useState("all");
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => animations.filter(animation => {
    return (character === "all" || animation.character_id === character)
      && (category === "all" || animation.category === category)
      && (status === "all" || animation.status === status)
      && (availability === "all" || (availability === "ready" ? animation.frame_count > 0 : animation.frame_count === 0))
      && (approval === "all" || String(animation.approved) === approval)
      && `${animation.name} ${animation.tags.join(" ")}`.toLowerCase().includes(query.toLowerCase());
  }), [animations, character, category, status, availability, approval, query]);
  const categories = [...new Set(animations.map(item => item.category))].sort();
  return <div className="space-y-5"><div className="grid gap-3 rounded-2xl border border-line bg-white p-4 md:grid-cols-3 xl:grid-cols-6"><Input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search motions…" className="md:col-span-2"/><Select aria-label="Character filter" value={character} onChange={event => setCharacter(event.target.value)}><option value="all">All characters</option>{characters.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</Select><Select aria-label="Category filter" value={category} onChange={event => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map(item => <option value={item} key={item}>{item.replaceAll("_", " ")}</option>)}</Select><Select aria-label="Frame availability filter" value={availability} onChange={event => setAvailability(event.target.value)}><option value="all">Any frame availability</option><option value="ready">Frames uploaded</option><option value="needed">Frames needed</option></Select><Select aria-label="Approval filter" value={approval} onChange={event => setApproval(event.target.value)}><option value="all">Any approval</option><option value="true">Approved</option><option value="false">Drafts</option></Select><Select aria-label="Status filter" value={status} onChange={event => setStatus(event.target.value)}><option value="all">All statuses</option><option>Frames needed</option><option>Draft</option><option>Needs review</option><option>Approved</option><option>Exported</option></Select></div>{filtered.length ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{filtered.map(animation => <SpriteCard key={animation.id} animation={animation}/>)}</div> : <EmptyState icon={Film} title="No animations match" description="Adjust the filters or create your first reusable DINKLY motion."/>}</div>;
}

