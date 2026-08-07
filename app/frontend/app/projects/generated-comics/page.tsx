"use client";

import Link from "next/link";
import { ArrowRight, ImageCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";

interface ArtReviewRecord {
  id: string;
  target_concept_id?: string | null;
  failures?: string[];
  recommendation?: string;
  reason?: string;
  created_at?: string;
}

export default function GeneratedComicsPage() {
  const [reviews, setReviews] = useState<ArtReviewRecord[]>([]);

  useEffect(() => {
    api<ArtReviewRecord[]>("/api/art-reviews").then(setReviews).catch(() => setReviews([]));
  }, []);

  return <div className="space-y-7">
    <PageHeader eyebrow="Projects" title="Generated comics" description="Artwork that has entered Art Reviewer QA lives here, with its exact repair or regeneration decision attached." actions={<Button asChild><Link href="/art-review">Review new artwork</Link></Button>}/>
    {reviews.length ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {[...reviews].reverse().map(review => <Card key={review.id} className="border-black/[0.055] shadow-none"><CardContent className="p-6"><div className="flex items-start justify-between gap-4"><div><p className="text-[10px] font-bold uppercase tracking-[.16em] text-muted">Art Reviewer record</p><h2 className="mt-2 font-semibold capitalize">{review.recommendation || "Review pending"}</h2></div><div className="rounded-xl bg-[#e1ecdc] p-2"><ImageCheck className="size-4 text-[#55775b]"/></div></div><p className="mt-4 text-sm leading-6 text-muted">{review.reason || "This generation has a saved QA record."}</p><div className="mt-5 flex flex-wrap gap-1.5">{(review.failures ?? []).slice(0, 4).map(failure => <span key={failure} className="rounded-full bg-wash px-2.5 py-1 text-[10px] font-semibold text-muted">{failure}</span>)}</div><Button asChild variant="ghost" size="sm" className="mt-4 -ml-3"><Link href="/art-review">Open Art Reviewer <ArrowRight className="size-3.5"/></Link></Button></CardContent></Card>)}
    </div> : <Card className="border-black/[0.055] shadow-none"><CardContent className="p-6"><EmptyState icon={ImageCheck} title="No generated comics are waiting" description="Upload a Nano Banana result to Art Reviewer. The saved QA decision will appear here without moving or changing the original file." action={<div className="flex flex-wrap justify-center gap-2"><Button asChild><Link href="/art-review">Review artwork</Link></Button><Button asChild variant="outline"><Link href="/prompt-builder">Build a prompt</Link></Button></div>}/></CardContent></Card>}
  </div>;
}
