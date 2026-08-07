"use client";

import { useState } from "react";

import { spriteAssetUrl } from "@/lib/api";
import type { SpriteFrame } from "@/lib/types";
import { Input } from "@/components/ui/input";

export function OnionSkinPreview({ frames, selectedIndex }: { frames: SpriteFrame[]; selectedIndex: number }) {
  const [enabled, setEnabled] = useState(false);
  const [previous, setPrevious] = useState(true);
  const [next, setNext] = useState(true);
  const [previousOpacity, setPreviousOpacity] = useState(0.22);
  const [nextOpacity, setNextOpacity] = useState(0.16);
  const active = frames[selectedIndex];
  return <div className="rounded-xl border border-line p-4"><div className="flex items-center justify-between"><div><p className="text-sm font-semibold">Onion skin</p><p className="text-xs text-muted">Alignment aid only—no drawing tools.</p></div><label className="flex items-center gap-2 text-xs font-semibold"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)}/> Enabled</label></div>{enabled && active && <><div className="relative mx-auto mt-4 aspect-square max-w-xs overflow-hidden rounded-xl bg-wash">{previous && frames[selectedIndex - 1] && <img src={spriteAssetUrl(frames[selectedIndex - 1].asset_url)} alt="Previous frame" className="absolute inset-0 h-full w-full object-contain" style={{ opacity: previousOpacity }}/>}<img src={spriteAssetUrl(active.asset_url)} alt="Current frame" className="absolute inset-0 h-full w-full object-contain"/>{next && frames[selectedIndex + 1] && <img src={spriteAssetUrl(frames[selectedIndex + 1].asset_url)} alt="Next frame" className="absolute inset-0 h-full w-full object-contain" style={{ opacity: nextOpacity }}/>}</div><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-xs"><span className="flex justify-between"><span>Previous opacity</span><input type="checkbox" checked={previous} onChange={event => setPrevious(event.target.checked)}/></span><Input type="range" min="0" max="0.8" step="0.05" value={previousOpacity} onChange={event => setPreviousOpacity(Number(event.target.value))}/></label><label className="text-xs"><span className="flex justify-between"><span>Next opacity</span><input type="checkbox" checked={next} onChange={event => setNext(event.target.checked)}/></span><Input type="range" min="0" max="0.8" step="0.05" value={nextOpacity} onChange={event => setNextOpacity(Number(event.target.value))}/></label></div></>}</div>;
}

