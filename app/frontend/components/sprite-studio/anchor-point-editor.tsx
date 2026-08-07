"use client";

import { Crosshair } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { SpriteFrame } from "@/lib/types";

export function AnchorPointEditor({ frame, onChange, onAlignSelected, onAlignBottom }: { frame?: SpriteFrame; onChange: (values: Partial<SpriteFrame>) => void; onAlignSelected: () => void; onAlignBottom: () => void }) {
  if (!frame) return <div className="rounded-xl border border-line p-5 text-sm text-muted">Select a frame to inspect its anchor and floor alignment.</div>;
  return <div className="space-y-4"><div className="relative mx-auto aspect-square max-w-xs overflow-hidden rounded-xl border border-line bg-wash"><div className="absolute inset-x-0 bottom-[10%] border-t border-dashed border-orange-500"/><div className="absolute inset-y-0 left-1/2 border-l border-dashed border-black/20"/><div className="absolute size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink bg-mustard" style={{ left: `${frame.anchor_x * 100}%`, top: `${frame.anchor_y * 100}%` }}><Crosshair className="size-3"/></div><div className="absolute inset-8 rounded-full border border-dashed border-black/20"/><span className="absolute bottom-2 left-2 text-[10px] font-semibold text-orange-700">Floor guide</span></div><div className="grid grid-cols-2 gap-3"><NumberField label="Anchor X" value={frame.anchor_x} min={0} max={1} step={0.01} onChange={value => onChange({ anchor_x: value })}/><NumberField label="Anchor Y" value={frame.anchor_y} min={0} max={1} step={0.01} onChange={value => onChange({ anchor_y: value })}/><NumberField label="X offset" value={frame.offset_x} onChange={value => onChange({ offset_x: value })}/><NumberField label="Y offset" value={frame.offset_y} onChange={value => onChange({ offset_y: value })}/></div><div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" onClick={onAlignSelected}>Align all to selected</Button><Button type="button" size="sm" variant="outline" onClick={onAlignBottom}>Align all to bottom center</Button></div></div>;
}

function NumberField({ label, value, onChange, min, max, step = 1 }: { label: string; value: number; onChange: (value: number) => void; min?: number; max?: number; step?: number }) { return <div><Label className="text-xs">{label}</Label><Input type="number" value={value} min={min} max={max} step={step} onChange={event => onChange(Number(event.target.value))}/></div>; }

