"use client";

import Link from "next/link";
import { ArrowRight, FileCheck2 } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";

interface PromptRecord {
  id: string;
  title: string;
  format: string;
  status: string;
  approved_by?: string | null;
  approved_at?: string | null;
  qa_notes?: string | null;
}

export default function ApprovedComicsPage() {
  const [approved, setApproved] = useState<PromptRecord[]>([]);

  useEffect(() => {
    api<PromptRecord[]>("/api/prompts").then(items => setApproved(items.filter(item => item.status === "approved"))).catch(() => setApproved([]));
  }, []);

  return <div className="space-y-7">
    <PageHeader eyebrow="Projects" title="Approved comics" description="The approved production records that are ready to guide final DINKLY artwork. Prompt approval is shown honestly; artwork still requires human visual approval." actions={<Button asChild variant="outline"><Link href="/examples">Open approved examples</Link></Button>}/>
    <div className="rounded-2xl bg-[#e1ecdc] px-5 py-4 text-sm leading-6 text-[#405444]">A production prompt can be approved here without implying that an unseen generated image has passed Art Reviewer QA.</div>
    {approved.length ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {approved.map(prompt => <Card key={prompt.id} className="border-black/[0.055] shadow-none"><CardContent className="p-6"><div className="flex items-start justify-between gap-4"><div><p className="text-[10px] font-bold uppercase tracking-[.16em] text-[#55775b]">Approved production record</p><h2 className="mt-2 font-semibold leading-6">{prompt.title}</h2></div><FileCheck2 className="size-5 shrink-0 text-[#55775b]"/></div><p className="mt-4 text-xs text-muted">{prompt.format} · approved by {prompt.approved_by || "creative team"}</p>{prompt.qa_notes && <p className="mt-3 text-sm leading-6 text-muted">{prompt.qa_notes}</p>}<Button asChild variant="ghost" size="sm" className="mt-4 -ml-3"><Link href="/prompt-builder">Open in Prompt Engineer <ArrowRight className="size-3.5"/></Link></Button></CardContent></Card>)}
    </div> : <Card className="border-black/[0.055] shadow-none"><CardContent className="p-6"><EmptyState icon={FileCheck2} title="Nothing has been approved yet" description="Approve a production prompt after creative review. Final generated artwork should still pass Art Reviewer QA before publication." action={<Button asChild><Link href="/prompt-builder">Open Prompt Engineer</Link></Button>}/></CardContent></Card>}
  </div>;
}
