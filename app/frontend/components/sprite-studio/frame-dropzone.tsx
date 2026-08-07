"use client";

import { UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function FrameDropzone({ onFiles, label = "Upload individual frames", multiple = true }: { onFiles: (files: File[]) => void; label?: string; multiple?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  function accept(files: FileList | null) { const accepted = Array.from(files ?? []).filter(file => ["image/png", "image/webp"].includes(file.type)); if (accepted.length) onFiles(accepted); }
  return <div onDragEnter={event => { event.preventDefault(); setDragging(true); }} onDragOver={event => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); accept(event.dataTransfer.files); }} className={cn("rounded-2xl border border-dashed p-7 text-center transition", dragging ? "border-ink bg-mustard/15" : "border-line bg-wash/50")} data-testid="frame-dropzone"><UploadCloud className="mx-auto size-7 text-muted"/><p className="mt-3 text-sm font-semibold">{label}</p><p className="mt-1 text-xs leading-5 text-muted">Transparent PNG or WEBP · consistent canvas size · safe filenames</p><input ref={input} type="file" accept="image/png,image/webp" multiple={multiple} className="hidden" onChange={event => accept(event.target.files)}/><Button type="button" variant="outline" size="sm" className="mt-4" onClick={() => input.current?.click()}>Choose files</Button></div>;
}

