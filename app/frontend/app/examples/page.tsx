"use client";
import { FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { PageHeader } from "@/components/page-header";
import { cn } from "@/lib/utils";

interface Example { slug: string; title: string; excerpt: string; content: string; path: string }
export default function ExamplesPage() { const [examples, setExamples] = useState<Example[]>([]); const [active, setActive] = useState<Example>(); useEffect(() => { api<Example[]>("/api/examples").then(items => { setExamples(items); setActive(items[0]); }); }, []); return <div className="space-y-7"><PageHeader eyebrow="Approved patterns" title="Examples" description="Production examples show how the system turns emotional simplicity into clear scenes and constrained prompts."/><div className="grid gap-5 lg:grid-cols-[260px_1fr]"><Card className="h-fit"><CardContent className="space-y-1 p-2">{examples.map(example => <Button key={example.slug} variant="ghost" className={cn("h-auto w-full justify-start px-3 py-3 text-left", active?.slug === example.slug && "bg-mustard")} onClick={() => setActive(example)}>{example.title}</Button>)}</CardContent></Card><Card><CardContent className="p-6 lg:p-8">{active ? <MarkdownViewer content={active.content}/> : <EmptyState icon={FileText} title="No examples found" description="Add approved markdown examples under EXAMPLES/."/>}</CardContent></Card></div></div>; }
