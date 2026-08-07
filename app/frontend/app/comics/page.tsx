"use client";

import Image from "next/image";
import Link from "next/link";
import { AlertCircle, ArrowRight, ImageIcon, RefreshCw, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import { comicModel, comicStatus, comicThumbnail, filterComics, type ComicDisplayStatus } from "@/lib/comics";
import type { GenerationRun } from "@/lib/types";

const statuses: Array<"All" | ComicDisplayStatus> = ["All", "Approved", "Waiting for Approval", "Passed", "Draft", "Cancelled", "Failed"];

export default function ComicsPage() {
  const [runs, setRuns] = useState<GenerationRun[]>();
  const [loadError, setLoadError] = useState<string>();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"All" | ComicDisplayStatus>("All");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const loadRuns = useCallback(() => {
    setRuns(undefined);
    setLoadError(undefined);
    void api<GenerationRun[]>("/api/generation-engine/history")
      .then(setRuns)
      .catch((error: unknown) => {
        setLoadError(error instanceof Error ? error.message : "The Generation Engine is unavailable.");
        setRuns([]);
      });
  }, []);
  useEffect(loadRuns, [loadRuns]);
  const visible = useMemo(() => [...filterComics(runs ?? [], query, status)].sort((a, b) => {
    const delta = new Date(b.started_at).getTime() - new Date(a.started_at).getTime();
    return sort === "newest" ? delta : -delta;
  }), [query, runs, sort, status]);

  return <div className="mx-auto max-w-7xl space-y-7 pb-16">
    <header><p className="text-[10px] font-bold uppercase tracking-[.2em] text-[#8c6325]">Generation library</p><h1 className="mt-3 text-4xl font-semibold tracking-[-.045em]">Comics</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-muted">Everything DINKLY has created.</p></header>
    <section aria-label="Comic filters" className="grid gap-3 rounded-2xl border border-line bg-white p-4 md:grid-cols-[1fr_220px_160px]">
      <label className="relative"><span className="sr-only">Search comics</span><Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted"/><Input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search comics..." className="pl-9"/></label>
      <Select aria-label="Filter by status" value={status} onChange={event => setStatus(event.target.value as "All" | ComicDisplayStatus)}>{statuses.map(value => <option key={value}>{value}</option>)}</Select>
      <Select aria-label="Sort comics" value={sort} onChange={event => setSort(event.target.value as "newest" | "oldest")}><option value="newest">Newest</option><option value="oldest">Oldest</option></Select>
    </section>
    {!runs && <p className="text-sm text-muted">Opening the comic library…</p>}
    {loadError && <Card><CardContent className="py-16 text-center"><AlertCircle className="mx-auto size-7 text-[#a14b3f]"/><h2 className="mt-4 text-xl font-semibold">Comic library unavailable</h2><p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted">{loadError}</p><Button className="mt-5" variant="outline" onClick={loadRuns}><RefreshCw className="size-4"/>Retry</Button></CardContent></Card>}
    {runs && !loadError && !visible.length && <Card><CardContent className="py-16 text-center"><ImageIcon className="mx-auto size-7 text-muted"/><h2 className="mt-4 text-xl font-semibold">No comics match</h2><p className="mt-2 text-sm text-muted">Try another search or status.</p></CardContent></Card>}
    <section aria-label="Comic gallery" className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">{visible.map(run => <ComicCard key={run.id} run={run}/>)}</section>
  </div>;
}

function ComicCard({ run }: { run: GenerationRun }) {
  const image = comicThumbnail(run); const status = comicStatus(run);
  return <Link href={`/comics/${run.id}`} className="group block"><Card className="h-full overflow-hidden transition group-hover:-translate-y-0.5 group-hover:border-[#b58b24] group-hover:shadow-md"><div className="relative aspect-square bg-wash">{image ? <Image src={image} alt={run.concept_text} fill unoptimized className="object-contain"/> : <div className="flex size-full items-center justify-center text-xs text-muted">Image unavailable</div>}</div><CardContent className="space-y-3 p-5"><div className="flex items-center justify-between gap-3"><Badge>{status}</Badge><span className="text-[10px] capitalize text-muted">{run.source_channel ?? "web"}</span></div><div><h2 className="line-clamp-2 text-lg font-semibold leading-6">{run.concept_text}</h2><p className="mt-1 text-[11px] text-muted">{comicModel(run)}</p></div><div className="flex items-center justify-between text-[10px] text-muted"><time>{new Date(run.started_at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</time><span className="flex items-center gap-1 font-semibold text-ink">Open <ArrowRight className="size-3"/></span></div></CardContent></Card></Link>;
}
