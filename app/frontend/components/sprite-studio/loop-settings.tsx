"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import type { SpriteLoopMode } from "@/lib/types";

export function LoopSettings({ loopMode, onLoopMode, frameRate, onFrameRate, loopStart, loopEnd, frameCount, onLoopStart, onLoopEnd, holdFirst, holdLast, onHoldFirst, onHoldLast }: { loopMode: SpriteLoopMode; onLoopMode: (value: SpriteLoopMode) => void; frameRate: number; onFrameRate: (value: number) => void; loopStart?: number; loopEnd?: number; frameCount?: number; onLoopStart?: (value: number) => void; onLoopEnd?: (value: number) => void; holdFirst: number; holdLast: number; onHoldFirst: (value: number) => void; onHoldLast: (value: number) => void }) {
  const total = Math.max(1, frameCount ?? 1);
  return <div className="grid gap-3 sm:grid-cols-2"><Field label="Loop mode"><Select data-testid="loop-selection" value={loopMode} onChange={event => onLoopMode(event.target.value as SpriteLoopMode)}><option value="loop">Loop</option><option value="ping_pong">Ping pong</option><option value="play_once">Play once</option><option value="hold_last">Hold last</option></Select></Field><Field label="Frame rate"><Input type="number" min="1" max="60" value={frameRate} onChange={event => onFrameRate(Number(event.target.value))}/></Field>{onLoopStart && <Field label="Loop start frame"><Input type="number" min="1" max={total} value={(loopStart ?? 0) + 1} onChange={event => onLoopStart(Math.max(0, Number(event.target.value) - 1))}/></Field>}{onLoopEnd && <Field label="Loop end frame"><Input type="number" min="1" max={total} value={(loopEnd ?? total - 1) + 1} onChange={event => onLoopEnd(Math.max(0, Number(event.target.value) - 1))}/></Field>}<Field label="Hold first frame (ms)"><Input type="number" min="0" value={holdFirst} onChange={event => onHoldFirst(Number(event.target.value))}/></Field><Field label="Hold last frame (ms)"><Input type="number" min="0" value={holdLast} onChange={event => onHoldLast(Number(event.target.value))}/></Field></div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <div className="space-y-1.5"><Label>{label}</Label>{children}</div>; }
