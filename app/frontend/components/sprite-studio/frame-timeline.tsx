"use client";

import { useState } from "react";

import { FrameThumbnail } from "@/components/sprite-studio/frame-thumbnail";
import type { SpriteFrame } from "@/lib/types";

export function FrameTimeline({ frames, selectedIds, onSelect, onReorder, onRemove, onDuplicate }: { frames: SpriteFrame[]; selectedIds: string[]; onSelect: (id: string, additive: boolean) => void; onReorder: (ids: string[]) => void; onRemove: (id: string) => void; onDuplicate?: (frame: SpriteFrame) => void }) {
  const [dragged, setDragged] = useState<string>();
  function drop(target: string) { if (!dragged || dragged === target) return; const ids = frames.map(item => item.id); const from = ids.indexOf(dragged); const to = ids.indexOf(target); ids.splice(to, 0, ids.splice(from, 1)[0]); onReorder(ids); setDragged(undefined); }
  return <div><div className="flex gap-3 overflow-x-auto pb-3" data-testid="frame-timeline">{frames.map(frame => <FrameThumbnail key={frame.id} frame={frame} selected={selectedIds.includes(frame.id)} onSelect={additive => onSelect(frame.id, additive)} onDuplicate={onDuplicate ? () => onDuplicate(frame) : undefined} onRemove={() => onRemove(frame.id)} onDragStart={() => setDragged(frame.id)} onDrop={() => drop(frame.id)}/>)}</div>{frames.length > 1 && <p className="mt-1 text-[11px] text-muted">Drag to reorder. Shift-click to select multiple frames.</p>}</div>;
}
