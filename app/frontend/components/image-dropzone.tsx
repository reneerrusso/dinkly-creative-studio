"use client";

import { ImagePlus, X } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";

export function ImageDropzone({
  onFile,
  title = "Drop a generated comic here",
  description = "PNG, JPG, JPEG, or WEBP. Stored locally.",
}: {
  onFile: (file: File | null) => void;
  title?: string;
  description?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);

  function choose(next: File | null) {
    setFile(next);
    onFile(next);
    if (!next && input.current) input.current.value = "";
  }

  return (
    <div
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        choose(event.dataTransfer.files[0] ?? null);
      }}
      className="rounded-2xl border border-dashed border-line bg-wash/45 p-6 text-center"
    >
      <input
        ref={input}
        className="hidden"
        type="file"
        accept=".png,.jpg,.jpeg,.webp"
        onChange={(event) => choose(event.target.files?.[0] ?? null)}
      />
      {file ? (
        <div className="flex items-center justify-between rounded-xl bg-white p-3 text-left">
          <div>
            <p className="text-sm font-semibold">{file.name}</p>
            <p className="text-xs text-muted">{Math.round(file.size / 1024)} KB</p>
          </div>
          <Button type="button" aria-label="Remove image" variant="ghost" size="icon" onClick={() => choose(null)}><X className="size-4" /></Button>
        </div>
      ) : (
        <>
          <ImagePlus className="mx-auto size-6 text-muted" />
          <p className="mt-3 text-sm font-semibold">{title}</p>
          <p className="mt-1 text-xs text-muted">{description}</p>
          <Button type="button" variant="outline" size="sm" className="mt-4" onClick={() => input.current?.click()}>Choose image</Button>
        </>
      )}
    </div>
  );
}
