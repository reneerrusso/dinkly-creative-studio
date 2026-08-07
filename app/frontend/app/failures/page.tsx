"use client";
import { AlertTriangle, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/loading-state";
import { PageHeader } from "@/components/page-header";
import { Select } from "@/components/ui/select";

interface Failure { name: string; category: string; why: string; prevention: string; when_to_simplify: string; edit_language: string; when_to_regenerate: string }
export default function FailuresPage() { const [failures, setFailures] = useState<Failure[]>(); const [query, setQuery] = useState(""); const [category, setCategory] = useState("all"); useEffect(() => { api<Failure[]>("/api/failures").then(setFailures).catch(() => setFailures([])); }, []); const categories = useMemo(() => [...new Set((failures ?? []).map(item => item.category))], [failures]); const filtered = useMemo(() => (failures ?? []).filter(item => (category === "all" || item.category === category) && `${item.name} ${item.why} ${item.prevention}`.toLowerCase().includes(query.toLowerCase())), [failures, category, query]); return <div className="space-y-7"><PageHeader eyebrow="Prevent" title="Failure library" description="Known generation failures, likely causes, precise prevention language, and clear thresholds for editing versus rebuilding."/><div className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 sm:flex-row"><div className="relative flex-1"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"/><Input className="pl-9" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search failures…"/></div><Select value={category} onChange={e => setCategory(e.target.value)} className="sm:w-56"><option value="all">All categories</option>{categories.map(value => <option key={value}>{value}</option>)}</Select></div>{!failures ? <LoadingState cards={6}/> : filtered.length ? <div className="grid gap-4 lg:grid-cols-2">{filtered.map(item => <Card key={item.name}><CardContent className="p-6"><Badge>{item.category}</Badge><h3 className="mt-3 text-lg font-semibold">{item.name}</h3><dl className="mt-4 space-y-3 text-sm leading-6"><Info label="Why the model misreads it" value={item.why}/><Info label="Prevention language" value={item.prevention}/><Info label="Targeted edit" value={item.edit_language}/><Info label="Regenerate when" value={item.when_to_regenerate}/></dl></CardContent></Card>)}</div> : <EmptyState icon={AlertTriangle} title="No failures match" description="Try a different category or search term."/>}</div>; }
function Info({ label, value }: { label: string; value: string }) { return <div><dt className="text-xs font-bold uppercase tracking-wide text-muted">{label}</dt><dd className="mt-1">{value}</dd></div>; }
