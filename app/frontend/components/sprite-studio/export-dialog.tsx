"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { SpriteAnimation, SpriteExport } from "@/lib/types";

export function ExportDialog({ animation, onExport }: { animation: SpriteAnimation; onExport?: (record: SpriteExport) => void }) {
  const [format, setFormat] = useState("horizontal");
  const [padding, setPadding] = useState(2);
  const [powerOfTwo, setPowerOfTwo] = useState(false);
  const [busy, setBusy] = useState(false);
  async function submit() { setBusy(true); try { const response = await api<{ export: SpriteExport }>("/api/sprite-sheets/export", { method: "POST", body: JSON.stringify({ animation_id: animation.id, export_format: format, padding, power_of_two: powerOfTwo }) }); onExport?.(response.export); toast.success("Sprite export created"); } catch (error) { toast.error(error instanceof Error ? error.message : "Export failed"); } finally { setBusy(false); } }
  return <Dialog><DialogTrigger asChild><Button type="button" variant="outline" disabled={!animation.frame_count}>Export</Button></DialogTrigger><DialogContent><DialogHeader><DialogTitle>Export {animation.name}</DialogTitle></DialogHeader><div className="space-y-4"><Field label="Format"><Select data-testid="sprite-export-format" value={format} onChange={event => setFormat(event.target.value)}><option value="horizontal">Horizontal sprite strip</option><option value="vertical">Vertical sprite strip</option><option value="grid">Grid sprite sheet</option><option value="individual_png">Individual PNG frames</option><option value="gif">Animated GIF</option><option value="webp">Animated WEBP</option><option value="metadata_json">Generic metadata JSON</option><option value="css">CSS steps animation</option><option value="react">React component</option><option value="remotion">Remotion asset</option><option value="canvas">Canvas helper</option></Select></Field><Field label="Transparent padding"><Select value={padding} onChange={event => setPadding(Number(event.target.value))}><option value={0}>0 px</option><option value={2}>2 px — default</option><option value={4}>4 px</option><option value={8}>8 px</option></Select></Field><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={powerOfTwo} onChange={event => setPowerOfTwo(event.target.checked)}/> Power-of-two sheet size</label>{!animation.approved && <p className="rounded-lg bg-orange-50 p-3 text-xs text-orange-800">This export will be labeled Draft and is not approved for production use.</p>}<Button type="button" onClick={submit} disabled={busy}>{busy ? "Exporting…" : "Create export"}</Button></div></DialogContent></Dialog>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <div className="space-y-1.5"><Label>{label}</Label>{children}</div>; }

