"use client";

import { useEffect, useState } from "react";

export function SpriteSheetPreview({ file, frameWidth, frameHeight, rows, columns, selectedCells, onToggle }: { file: File | null; frameWidth: number; frameHeight: number; rows: number; columns: number; selectedCells: number[]; onToggle: (cell: number) => void }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    if (!file) { setUrl(""); return; }
    const nextUrl = URL.createObjectURL(file);
    setUrl(nextUrl);
    return () => URL.revokeObjectURL(nextUrl);
  }, [file]);
  return <div className="space-y-3"><div className="relative overflow-hidden rounded-xl border border-line bg-wash">{url ? <img src={url} alt="Sprite sheet slicing preview" className="block h-auto w-full"/> : <div className="p-10 text-center text-sm text-muted">Choose a sprite sheet to preview its slicing grid.</div>}{url && <div className="absolute inset-0 grid" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)`, gridTemplateRows: `repeat(${rows}, 1fr)` }}>{Array.from({ length: rows * columns }, (_, cell) => <button type="button" key={cell} aria-label={`Toggle cell ${cell + 1}`} onClick={() => onToggle(cell)} className={`border border-black/25 text-[10px] font-bold ${selectedCells.includes(cell) ? "bg-mustard/20" : "bg-black/35 text-white"}`}>{cell + 1}</button>)}</div>}</div><p className="text-xs text-muted">{frameWidth}×{frameHeight} px cells · {selectedCells.length} of {rows * columns} selected</p></div>;
}
