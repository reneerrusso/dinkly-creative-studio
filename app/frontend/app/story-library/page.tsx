"use client";

import { AlertTriangle, BookHeart, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { LoadingState } from "@/components/loading-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import { isNewStory, type StorySeed } from "@/lib/story-seed";

export default function StoryLibraryPage() {
  const [stories, setStories] = useState<StorySeed[]>();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [selected, setSelected] = useState<StorySeed>();

  useEffect(() => { api<StorySeed[]>("/api/story-library").then(setStories).catch(() => setStories([])); }, []);
  const categories = useMemo(() => [...new Set((stories ?? []).map((story) => story.category))].sort(), [stories]);
  const filtered = useMemo(
    () => (stories ?? []).filter((story) =>
      (category === "all" || story.category === category)
      && `${story.title_left} ${story.title_right} ${story.left_setting} ${story.right_setting} ${story.category}`.toLowerCase().includes(query.toLowerCase())),
    [stories, query, category],
  );

  return (
    <div className="space-y-7">
      <PageHeader eyebrow="Explore" title="Story library" description="Scene-rich relationship concepts with one clear setting, purposeful props, and a readable emotional contrast." />
      <div className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 sm:flex-row">
        <div className="relative flex-1"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" /><Input className="pl-9" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search scenes, settings, and storylines…" /></div>
        <Select value={category} onChange={(event) => setCategory(event.target.value)} className="sm:w-56"><option value="all">All categories</option>{categories.map((value) => <option key={value}>{value}</option>)}</Select>
      </div>

      {!stories ? <LoadingState cards={6} /> : filtered.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((story) => <StoryCard key={story.id} story={story} onOpen={() => setSelected(story)} />)}
        </div>
      ) : <EmptyState icon={BookHeart} title="No stories match" description="Try a broader setting, emotional theme, or category." />}

      <Dialog open={Boolean(selected)} onOpenChange={(open) => { if (!open) setSelected(undefined); }}>
        {selected && <StoryDetail story={selected} />}
      </Dialog>
    </div>
  );
}

function StoryCard({ story, onOpen }: { story: StorySeed; onOpen: () => void }) {
  const leftName = story.left_character === "girl" ? "Girl DINKLY" : "Boy DINKLY";
  return (
    <Card className="transition hover:-translate-y-0.5 hover:shadow-lg">
      <CardContent className="p-6">
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-wrap gap-2"><Badge>{story.category}</Badge>{isNewStory(story) && <Badge className="bg-emerald-100 text-emerald-800">New</Badge>}</div>
          <Richness value={story.scene_richness ?? "Sparse"} />
        </div>
        <h3 className="mt-4 text-lg font-semibold">{story.title_left} <span className="text-muted">/</span> {story.title_right}</h3>
        <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-muted">Left character</p>
        <p className="mt-1 text-sm">{leftName} alone</p>
        <p className="mt-3 line-clamp-2 text-sm leading-6 text-muted">{story.shared_environment}</p>
        <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-wash/60 p-3 text-xs leading-5">
          <p><strong>Left:</strong> <span className="text-muted">{story.left_character_action}</span></p>
          <p><strong>Right:</strong> <span className="text-muted">{story.right_character_actions}</span></p>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
          <ColorDot label={story.background_color ?? "warm cream"} />
          <ColorDot label={story.accent_color ?? "muted mustard"} />
          <span>{story.prop_count ?? 0} props max / panel</span>
          <span>{story.brand_friendly ? "Brand-friendly" : "Story-first"}</span>
        </div>
        {story.scene_warnings?.map((warning) => <p key={warning} className="mt-4 flex gap-2 rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-900"><AlertTriangle className="mt-0.5 size-3.5 shrink-0" />{warning}</p>)}
        <div className="mt-5 flex gap-2"><Button variant="outline" size="sm" onClick={onOpen}>View scene</Button><Button asChild size="sm"><Link href={`/generate?story=${encodeURIComponent(story.id)}`}>Use in Generation Engine</Link></Button></div>
      </CardContent>
    </Card>
  );
}

function StoryDetail({ story }: { story: StorySeed }) {
  return (
    <DialogContent className="max-w-3xl">
      <DialogHeader><div className="flex items-center gap-2"><Richness value={story.scene_richness ?? "Sparse"} /><Badge>{story.category}</Badge>{isNewStory(story) && <Badge className="bg-emerald-100 text-emerald-800">New</Badge>}</div><DialogTitle className="text-2xl font-semibold">{story.title_left} / {story.title_right}</DialogTitle><DialogDescription>{story.concept}</DialogDescription></DialogHeader>
      <div className="grid gap-5 md:grid-cols-2">
        <Panel title="Left panel" rows={[
          ["Character", story.left_character === "girl" ? "Girl DINKLY" : "Boy DINKLY"],
          ["Action", story.left_character_action], ["Setting", story.left_setting],
          ["Props", story.left_props?.join(" · ") || "None defined"], ["Emotion", story.left_emotion],
        ]} />
        <Panel title="Right panel" rows={[
          ["Characters", "Boy DINKLY + Girl DINKLY"], ["Actions", story.right_character_actions],
          ["Setting", story.right_setting], ["Props", story.right_props?.join(" · ") || "None defined"],
          ["Emotion", story.right_emotion],
        ]} />
      </div>
      <Panel title="Shared visual system" rows={[
        ["Environment", story.shared_environment], ["Background", story.background_color],
        ["Accent color", story.accent_color], ["Camera angle", story.camera_angle],
        ["Environmental contrast", story.environmental_contrast],
        ["Execution risks", story.execution_risks?.join(" · ") || "None recorded"],
      ]} />
      {story.scene_warnings?.map((warning) => <p key={warning} className="flex gap-2 rounded-xl bg-amber-50 p-4 text-sm text-amber-900"><AlertTriangle className="mt-0.5 size-4 shrink-0" />{warning}</p>)}
      <Button asChild className="mt-1"><Link href={`/generate?story=${encodeURIComponent(story.id)}`}>Use in Generation Engine</Link></Button>
    </DialogContent>
  );
}

function Panel({ title, rows }: { title: string; rows: Array<[string, string | undefined]> }) {
  return <section className="rounded-xl border border-line p-4"><h4 className="text-xs font-bold uppercase tracking-wider">{title}</h4><dl className="mt-3 space-y-3">{rows.map(([label, value]) => <div key={label}><dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</dt><dd className="mt-1 text-sm leading-6">{value || "Not defined"}</dd></div>)}</dl></section>;
}

function Richness({ value }: { value: "Sparse" | "Balanced" | "Detailed" }) {
  const tone = value === "Balanced" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-900";
  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${tone}`}>Scene: {value}</span>;
}

function ColorDot({ label }: { label: string }) {
  return <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-full border border-black/10" style={{ backgroundColor: colorValue(label) }} />{label}</span>;
}

function colorValue(name: string) {
  const map: Record<string, string> = { "warm cream": "#f7e8c1", "pastel peach": "#f4c8ae", "dusty blue": "#afd7ef", "soft lavender": "#c6b8ee", mint: "#bfe4d1", "warm sage": "#cbd3af", "butter yellow": "#f4df8b", "dusty rose": "#dfb3ba", "warm sand": "#e5c99f", "blush pink": "#efc2c8", "powder blue": "#bdddf0" };
  return map[name] ?? "#e7e1d6";
}
