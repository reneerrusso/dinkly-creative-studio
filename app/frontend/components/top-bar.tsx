"use client";

import Link from "next/link";
import { Search } from "lucide-react";
import { useEffect, useState } from "react";

import { Input } from "@/components/ui/input";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { api } from "@/lib/api";

interface SearchResult { type: string; title: string; excerpt: string; href: string }

export function TopBar() {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query);
  const [results, setResults] = useState<SearchResult[]>([]);
  useEffect(() => { if (debouncedQuery.trim().length < 2) { setResults([]); return; } api<SearchResult[]>(`/api/search?q=${encodeURIComponent(debouncedQuery)}`).then(setResults).catch(() => setResults([])); }, [debouncedQuery]);
  return <header className="sticky top-0 z-30 flex min-h-16 items-center gap-3 border-b border-black/[0.055] bg-[#f8f6f0]/92 px-4 py-2 backdrop-blur sm:px-6 lg:px-8">
    <div className="w-9 shrink-0 lg:hidden"/>
    <div className="relative mx-auto hidden w-full max-w-lg md:block"><Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted"/><Input aria-label="Search the DINKLY brain" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search the DINKLY brain…" className="h-9 border-black/[0.06] bg-white/75 pl-9 text-xs shadow-none"/>{results.length > 0 && <div className="absolute top-11 z-50 w-full overflow-hidden rounded-xl border border-line bg-white shadow-xl">{results.slice(0, 6).map((result, index) => <Link key={`${result.type}-${index}`} href={result.href || "#"} onClick={() => { setQuery(""); setResults([]); }} className="block border-b border-line p-3 last:border-0 hover:bg-wash"><div className="flex items-center justify-between gap-3"><p className="text-sm font-semibold">{result.title}</p><span className="text-[9px] uppercase tracking-wide text-muted">{result.type}</span></div><p className="mt-1 line-clamp-1 text-xs text-muted">{result.excerpt}</p></Link>)}</div>}</div>
    <div className="w-9 shrink-0"/>
  </header>;
}
