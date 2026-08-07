"use client";

import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

export default function UsedStorylinesPage() {
  const [records, setRecords] = useState<Array<Record<string, any>>>([]);
  const [query, setQuery] = useState("");
  useEffect(() => { api<Array<Record<string, any>>>("/api/concept-generator/used-storylines").then(setRecords).catch(() => setRecords([])); }, []);
  const filtered = useMemo(() => records.filter(item => JSON.stringify(item.concept).toLowerCase().includes(query.toLowerCase())), [records, query]);
  return <div className="mx-auto max-w-5xl space-y-6"><header><p className="text-[10px] font-bold uppercase tracking-[.2em] text-muted">Originality memory</p><h1 className="mt-2 text-4xl font-semibold tracking-[-.04em]">Used Storylines</h1><p className="mt-3 text-sm text-muted">Approved production stories stay visible so future generation does not silently repeat them.</p></header><div className="relative"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" /><Input className="pl-9" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search used storylines…" /></div><div className="space-y-3">{filtered.map(item => <div key={item.id} className="rounded-2xl border border-line bg-white p-5"><p className="font-semibold">{item.concept.story_title ?? `${item.concept.title_left ?? "Story"} / ${item.concept.title_right ?? ""}`}</p><p className="mt-1 text-xs text-muted">Used {new Date(item.date_used).toLocaleDateString()} · {String(item.format).replaceAll("_", " ")}</p></div>)}{!filtered.length && <p className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-muted">No used storylines match.</p>}</div></div>;
}
