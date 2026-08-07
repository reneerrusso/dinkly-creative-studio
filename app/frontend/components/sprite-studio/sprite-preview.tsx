"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { AnimationControls } from "@/components/sprite-studio/animation-controls";
import { Select } from "@/components/ui/select";
import { spriteAssetUrl } from "@/lib/api";
import type { SpriteFrame, SpriteLoopMode } from "@/lib/types";

const backgrounds: Record<string, string> = { checkerboard: "transparent", "warm cream": "#f7e8c1", "pastel peach": "#f4c8ae", "dusty blue": "#afd7ef", "soft lavender": "#c6b8ee", "warm sage": "#cbd3af", "dark navy": "#18212a" };

export function SpritePreview({ frames, frameRate, loopMode = "loop" }: { frames: SpriteFrame[]; frameRate: number; loopMode?: SpriteLoopMode }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loop, setLoop] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [background, setBackground] = useState("checkerboard");
  const [pixelPerfect, setPixelPerfect] = useState(false);
  const [scale, setScale] = useState(1);
  const [direction, setDirection] = useState(1);
  const frame = frames[index];
  const duration = useMemo(() => frames.reduce((total, item) => total + item.duration_ms, 0), [frames]);
  useEffect(() => { if (index >= frames.length) setIndex(0); }, [frames.length, index]);
  useEffect(() => {
    if (!frame || !canvas.current) return;
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => { const ctx = canvas.current?.getContext("2d"); if (!ctx || !canvas.current) return; ctx.clearRect(0, 0, canvas.current.width, canvas.current.height); ctx.imageSmoothingEnabled = !pixelPerfect; const width = image.width * scale; const height = image.height * scale; ctx.globalAlpha = frame.opacity; ctx.drawImage(image, (canvas.current.width - width) / 2 + frame.offset_x, canvas.current.height - height + frame.offset_y, width, height); };
    image.src = spriteAssetUrl(frame.asset_url);
  }, [frame, pixelPerfect, scale]);
  useEffect(() => {
    if (!playing || !frames.length) return;
    const delay = Math.max(16, (frame?.duration_ms ?? 1000 / frameRate) / speed);
    const timer = window.setTimeout(() => setIndex(current => {
      if (loopMode === "ping_pong") { const next = current + direction; if (next >= frames.length || next < 0) { setDirection(value => -value); return current - direction; } return next; }
      if (current + 1 >= frames.length) { if (loop && loopMode !== "hold_last" && loopMode !== "play_once") return 0; setPlaying(false); return frames.length - 1; }
      return current + 1;
    }), delay);
    return () => window.clearTimeout(timer);
  }, [playing, frames.length, frame?.duration_ms, frameRate, speed, loop, loopMode, direction]);
  return <div className="space-y-4"><div className={`relative flex aspect-square max-h-[460px] items-center justify-center overflow-hidden rounded-2xl border border-line ${background === "checkerboard" ? "bg-[linear-gradient(45deg,#eee_25%,transparent_25%),linear-gradient(-45deg,#eee_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#eee_75%),linear-gradient(-45deg,transparent_75%,#eee_75%)] bg-[length:24px_24px] bg-[position:0_0,0_12px,12px_-12px,-12px_0px]" : ""}`} style={background !== "checkerboard" ? { backgroundColor: backgrounds[background] } : undefined}><canvas ref={canvas} width={512} height={512} className="h-full w-full"/>{!frames.length && <p className="absolute text-sm text-muted">Upload approved frames to bring this animation to life.</p>}</div><AnimationControls playing={playing} onPlayPause={() => setPlaying(value => !value)} onRestart={() => { setIndex(0); setPlaying(true); }} onPrevious={() => setIndex(value => Math.max(0, value - 1))} onNext={() => setIndex(value => frames.length ? Math.min(frames.length - 1, value + 1) : 0)} speed={speed} onSpeed={setSpeed} loop={loop} onLoop={setLoop}/><div className="grid gap-3 text-xs sm:grid-cols-3"><Select aria-label="Preview background" value={background} onChange={event => setBackground(event.target.value)}>{Object.keys(backgrounds).map(item => <option key={item}>{item}</option>)}</Select><Select aria-label="Preview scale" value={scale} onChange={event => setScale(Number(event.target.value))}><option value={0.5}>50%</option><option value={1}>100%</option><option value={1.5}>150%</option><option value={2}>200%</option></Select><label className="flex items-center gap-2 rounded-lg border border-line px-3"><input type="checkbox" checked={pixelPerfect} onChange={event => setPixelPerfect(event.target.checked)}/> Pixel-perfect</label></div><div className="grid grid-cols-2 gap-2 rounded-xl bg-wash p-3 text-[11px] sm:grid-cols-5"><Info label="Frame" value={frames.length ? `${index + 1}/${frames.length}` : "0/0"}/><Info label="Timestamp" value={`${frames.slice(0, index).reduce((sum, item) => sum + item.duration_ms, 0)} ms`}/><Info label="Rate" value={`${frameRate} fps`}/><Info label="Loop" value={`${duration} ms`}/><Info label="Canvas" value={frame ? `${frame.width}×${frame.height}` : "—"}/></div></div>;
}

function Info({ label, value }: { label: string; value: string }) { return <div><span className="text-muted">{label}</span><strong className="mt-0.5 block">{value}</strong></div>; }
