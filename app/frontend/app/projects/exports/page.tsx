"use client";

import Link from "next/link";
import { Download, FileText } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api, getSpriteExports } from "@/lib/api";
import type { SpriteExport } from "@/lib/types";

interface PromptRecord { id: string; title: string; format: string; status: string; created_at?: string }

export default function ExportsPage() {
  const [exports, setExports] = useState<SpriteExport[]>([]);
  const [prompts, setPrompts] = useState<PromptRecord[]>([]);

  useEffect(() => {
    Promise.all([
      getSpriteExports().catch(() => []),
      api<PromptRecord[]>("/api/prompts").catch(() => []),
    ]).then(([spriteExports, promptRecords]) => {
      setExports(spriteExports);
      setPrompts(promptRecords);
    });
  }, []);

  return <div className="space-y-7">
    <PageHeader eyebrow="Projects" title="Exports" description="A quiet handoff room for immutable motion exports and saved Prompt Engineer records." actions={<div className="flex gap-2"><Button asChild variant="outline"><Link href="/sprite-studio/exports">Motion exports</Link></Button><Button asChild><Link href="/prompt-builder">New prompt</Link></Button></div>}/>
    <div className="grid gap-5 xl:grid-cols-2">
      <Card className="border-black/[0.055] shadow-none"><CardContent className="p-6"><div className="flex items-center justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[.17em] text-muted">Motion Director</p><h2 className="mt-2 text-lg font-semibold">Sprite exports</h2></div><Download className="size-5 text-muted"/></div>{exports.length ? <div className="mt-5 divide-y divide-black/[0.06]">{[...exports].reverse().slice(0, 6).map(item => <div key={item.id} className="py-4 first:pt-0 last:pb-0"><p className="text-sm font-semibold">{item.animation_name}</p><p className="mt-1 text-xs text-muted">{item.character} · {item.export_format} · {item.frame_count} frames</p><p className="mt-1 text-[10px] text-muted">{item.official_use ? "Approved for official use" : item.warning || "Draft export"}</p></div>)}</div> : <div className="mt-5"><EmptyState icon={Download} title="No motion exports" description="Approved sprite sheets and code handoffs will appear here." action={<Button asChild variant="outline"><Link href="/sprite-studio/exports">Open Sprite Exports</Link></Button>}/></div>}</CardContent></Card>
      <Card className="border-black/[0.055] shadow-none"><CardContent className="p-6"><div className="flex items-center justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[.17em] text-muted">Prompt Engineer</p><h2 className="mt-2 text-lg font-semibold">Prompt history</h2></div><FileText className="size-5 text-muted"/></div>{prompts.length ? <div className="mt-5 divide-y divide-black/[0.06]">{prompts.slice(0, 6).map(item => <div key={item.id} className="py-4 first:pt-0 last:pb-0"><p className="text-sm font-semibold">{item.title}</p><p className="mt-1 text-xs text-muted">{item.format} · {item.status}</p></div>)}</div> : <div className="mt-5"><EmptyState icon={FileText} title="No saved prompts" description="Save a draft or approved prompt with Prompt Engineer and its record will appear here." action={<Button asChild variant="outline"><Link href="/prompt-builder">Open Prompt Engineer</Link></Button>}/></div>}</CardContent></Card>
    </div>
  </div>;
}
