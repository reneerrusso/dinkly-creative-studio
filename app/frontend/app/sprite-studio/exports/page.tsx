"use client";

import Link from "next/link";
import { ArrowLeft, Download, FileJson } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { LoadingState } from "@/components/loading-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getSpriteExports, spriteAssetUrl } from "@/lib/api";
import type { SpriteExport } from "@/lib/types";

export default function SpriteExportsPage() {
  const [exports, setExports] = useState<SpriteExport[]>();
  const [error, setError] = useState("");
  useEffect(() => { getSpriteExports().then(setExports).catch((reason: Error) => setError(reason.message)); }, []);
  return <div className="space-y-7"><PageHeader eyebrow="Sprite Studio" title="Exports" description="Production files are versioned locally and never overwrite prior sheets, metadata, or runtime helpers." actions={<Button asChild variant="ghost"><Link href="/sprite-studio"><ArrowLeft className="size-4"/>Library</Link></Button>}/>{error && <ErrorState message={error}/>} {!exports && !error && <LoadingState cards={4}/>} {exports && (exports.length ? <div className="grid gap-4 md:grid-cols-2">{exports.map(record => <Card key={record.id}><CardContent className="p-5"><div className="flex items-start justify-between gap-3"><div><p className="text-xs text-muted">{record.character}</p><h2 className="mt-1 font-semibold">{record.animation_name}</h2></div><Badge>{record.official_use ? "Production approved" : "Draft export"}</Badge></div><div className="mt-4 grid grid-cols-3 gap-2 text-xs"><Metric label="Format" value={record.export_format.replaceAll("_", " ")}/><Metric label="Frames" value={String(record.frame_count)}/><Metric label="Canvas" value={`${record.frame_width}×${record.frame_height}`}/></div>{record.warning && <p className="mt-3 rounded-lg bg-orange-50 p-2 text-xs text-orange-800">{record.warning}</p>}<div className="mt-4 flex flex-wrap gap-2"><Button asChild size="sm" variant="outline"><a href={spriteAssetUrl(record.asset_url)} download><Download className="size-4"/>Asset</a></Button><Button asChild size="sm" variant="ghost"><a href={spriteAssetUrl(record.metadata_url)} target="_blank" rel="noreferrer"><FileJson className="size-4"/>Metadata</a></Button><Button asChild size="sm" variant="ghost"><Link href={`/sprite-studio/animations/${record.animation_id}`}>Open animation</Link></Button></div></CardContent></Card>)}</div> : <EmptyState icon={Download} title="No sprite exports yet" description="Approve or review an animation, then create a sprite sheet, GIF, WEBP, metadata file, or runtime helper."/> )}</div>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-lg bg-wash p-2"><span className="text-[10px] uppercase tracking-wide text-muted">{label}</span><strong className="mt-1 block capitalize">{value}</strong></div>; }

