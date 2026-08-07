import Link from "next/link";
import { ArrowUpRight, Frame } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { spriteAssetUrl } from "@/lib/api";
import type { SpriteAnimation } from "@/lib/types";

export function SpriteCard({ animation }: { animation: SpriteAnimation }) {
  const thumbnail = animation.frames?.[0]?.asset_url || animation.thumbnail_path || "";
  return <Card className="overflow-hidden transition hover:-translate-y-0.5 hover:shadow-md"><div className="flex aspect-[16/9] items-center justify-center border-b border-line bg-[linear-gradient(45deg,#eee_25%,transparent_25%),linear-gradient(-45deg,#eee_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#eee_75%),linear-gradient(-45deg,transparent_75%,#eee_75%)] bg-[length:18px_18px] bg-[position:0_0,0_9px,9px_-9px,-9px_0px]">{thumbnail ? <img src={spriteAssetUrl(thumbnail)} alt="" className="h-full w-full object-contain p-3"/> : <div className="text-center text-muted"><Frame className="mx-auto size-7"/><p className="mt-2 text-xs">Frames needed</p></div>}</div><CardContent className="p-5"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold text-muted">{animation.character?.name ?? "Asset group"}</p><h3 className="mt-1 font-semibold">{animation.name}</h3></div><Badge>{animation.status}</Badge></div><div className="mt-4 grid grid-cols-3 gap-2 text-xs"><Stat label="Frames" value={`${animation.frame_count}/${animation.expected_frame_count}`}/><Stat label="Duration" value={animation.duration_ms ? `${(animation.duration_ms / 1000).toFixed(1)}s` : "—"}/><Stat label="Loop" value={animation.loop_mode.replaceAll("_", " ")}/></div><div className="mt-4 flex items-center justify-between"><Badge className="capitalize">{animation.category.replaceAll("_", " ")}</Badge><Link href={`/sprite-studio/animations/${animation.id}`} className="inline-flex items-center gap-1 text-xs font-semibold">Open <ArrowUpRight className="size-3"/></Link></div></CardContent></Card>;
}

function Stat({ label, value }: { label: string; value: string }) { return <div><p className="text-[10px] uppercase tracking-wide text-muted">{label}</p><p className="mt-1 truncate font-semibold capitalize">{value}</p></div>; }

