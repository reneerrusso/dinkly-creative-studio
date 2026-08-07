"use client";

import { ChevronLeft, ChevronRight, Pause, Play, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";

export function AnimationControls({ playing, onPlayPause, onRestart, onPrevious, onNext, speed, onSpeed, loop, onLoop }: { playing: boolean; onPlayPause: () => void; onRestart: () => void; onPrevious: () => void; onNext: () => void; speed: number; onSpeed: (value: number) => void; loop: boolean; onLoop: (value: boolean) => void }) {
  return <div className="flex flex-wrap items-center gap-2"><Button size="icon" variant="outline" aria-label="Previous frame" onClick={onPrevious}><ChevronLeft className="size-4"/></Button><Button size="icon" aria-label={playing ? "Pause" : "Play"} onClick={onPlayPause}>{playing ? <Pause className="size-4"/> : <Play className="size-4"/>}</Button><Button size="icon" variant="outline" aria-label="Next frame" onClick={onNext}><ChevronRight className="size-4"/></Button><Button size="icon" variant="ghost" aria-label="Restart" onClick={onRestart}><RotateCcw className="size-4"/></Button><Select aria-label="Playback speed" value={speed} onChange={event => onSpeed(Number(event.target.value))} className="w-24"><option value={0.5}>0.5×</option><option value={1}>1×</option><option value={1.5}>1.5×</option><option value={2}>2×</option></Select><label className="ml-auto flex items-center gap-2 text-xs font-semibold"><input type="checkbox" checked={loop} onChange={event => onLoop(event.target.checked)}/> Loop</label></div>;
}

