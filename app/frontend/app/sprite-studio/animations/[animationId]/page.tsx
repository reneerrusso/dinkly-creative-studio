"use client";

import Link from "next/link";
import { ArrowLeft, Check, Film, ScanSearch, UploadCloud } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { ErrorState } from "@/components/error-state";
import { LoadingState } from "@/components/loading-state";
import { PageHeader } from "@/components/page-header";
import { AnchorPointEditor } from "@/components/sprite-studio/anchor-point-editor";
import { ExportDialog } from "@/components/sprite-studio/export-dialog";
import { FrameDropzone } from "@/components/sprite-studio/frame-dropzone";
import { FrameInspector } from "@/components/sprite-studio/frame-inspector";
import { FrameTimeline } from "@/components/sprite-studio/frame-timeline";
import { LoopSettings } from "@/components/sprite-studio/loop-settings";
import { OnionSkinPreview } from "@/components/sprite-studio/onion-skin-preview";
import { SpritePreview } from "@/components/sprite-studio/sprite-preview";
import { SpriteSheetPreview } from "@/components/sprite-studio/sprite-sheet-preview";
import { ValidationPanel } from "@/components/sprite-studio/validation-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, getSpriteAnimation } from "@/lib/api";
import type { SpriteAnimation, SpriteFrame, SpriteLoopMode } from "@/lib/types";

interface ValidationResult { status: string; issues: Array<{ frame_id: string | null; issue: string; severity: string }>; checklist: string[]; blocking: boolean }

export default function SpriteAnimationPage() {
  const { animationId } = useParams<{ animationId: string }>();
  const [animation, setAnimation] = useState<SpriteAnimation>();
  const [error, setError] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [validation, setValidation] = useState<ValidationResult>();
  const [frameRate, setFrameRate] = useState(8);
  const [loopMode, setLoopMode] = useState<SpriteLoopMode>("loop");
  const [loopStart, setLoopStart] = useState(0);
  const [loopEnd, setLoopEnd] = useState(0);
  const [holdFirst, setHoldFirst] = useState(0);
  const [holdLast, setHoldLast] = useState(0);
  const [batchDuration, setBatchDuration] = useState(125);
  const [sheet, setSheet] = useState<File | null>(null);
  const [frameWidth, setFrameWidth] = useState(256);
  const [frameHeight, setFrameHeight] = useState(256);
  const [rows, setRows] = useState(1);
  const [columns, setColumns] = useState(4);
  const [selectedCells, setSelectedCells] = useState([0, 1, 2, 3]);
  const [transparentBackground, setTransparentBackground] = useState(true);
  const load = () => getSpriteAnimation(animationId).then(record => { setAnimation(record); setFrameRate(record.frame_rate); setLoopMode(record.loop_mode); setLoopStart(record.loop_start_frame ?? 0); setLoopEnd(record.loop_end_frame ?? Math.max(0, record.frames.length - 1)); setHoldFirst(record.hold_first_frame_ms); setHoldLast(record.hold_last_frame_ms); if (!selectedIds.length && record.frames.length) setSelectedIds([record.frames[0].id]); }).catch((reason: Error) => setError(reason.message));
  useEffect(() => { load(); }, [animationId]);
  useEffect(() => { setSelectedCells(Array.from({ length: rows * columns }, (_, index) => index)); }, [rows, columns]);
  const selectedFrame = useMemo(() => animation?.frames.find(frame => frame.id === selectedIds[0]), [animation, selectedIds]);
  const selectedIndex = animation?.frames.findIndex(frame => frame.id === selectedFrame?.id) ?? 0;
  async function upload(files: File[]) { const form = new FormData(); files.forEach(file => form.append("files", file)); try { await api(`/api/sprite-animations/${animationId}/frames`, { method: "POST", body: form }); toast.success(`${files.length} frame${files.length === 1 ? "" : "s"} uploaded`); await load(); } catch (reason) { toast.error(reason instanceof Error ? reason.message : "Upload failed"); } }
  async function importSheet() { if (!sheet) return toast.error("Choose a sprite sheet"); const form = new FormData(); form.append("file", sheet); form.append("animation_id", animationId); form.append("frame_width", String(frameWidth)); form.append("frame_height", String(frameHeight)); form.append("row_count", String(rows)); form.append("column_count", String(columns)); form.append("selected_cells", JSON.stringify(selectedCells)); form.append("transparent_background", String(transparentBackground)); try { await api("/api/sprite-sheets/import", { method: "POST", body: form }); toast.success("Sprite sheet sliced into frames"); setSheet(null); await load(); } catch (reason) { toast.error(reason instanceof Error ? reason.message : "Import failed"); } }
  async function updateFrame(id: string, changes: Partial<SpriteFrame>) { try { await api(`/api/sprite-frames/${id}`, { method: "PUT", body: JSON.stringify(changes) }); await load(); } catch (reason) { toast.error(reason instanceof Error ? reason.message : "Frame update failed"); } }
  async function removeFrame(id: string) { if (!window.confirm("Remove this frame from the animation? The source file will remain locally recoverable.")) return; await api(`/api/sprite-frames/${id}`, { method: "DELETE" }); setSelectedIds(values => values.filter(value => value !== id)); await load(); }
  async function duplicateFrame(frame: SpriteFrame) { await api(`/api/sprite-frames/${frame.id}/duplicate`, { method: "POST", body: "{}" }); toast.success("Frame duplicated for timing"); await load(); }
  async function reorder(ids: string[]) { await api(`/api/sprite-animations/${animationId}/reorder`, { method: "POST", body: JSON.stringify({ frame_ids: ids }) }); await load(); }
  async function align(mode: "bottom_center" | "selected_frame") { await api(`/api/sprite-animations/${animationId}/align`, { method: "POST", body: JSON.stringify({ mode, selected_frame_id: mode === "selected_frame" ? selectedFrame?.id : null }) }); toast.success("Frames aligned"); await load(); }
  async function saveLoop() { if (loopEnd < loopStart) return toast.error("Loop end must be at or after loop start"); await api(`/api/sprite-animations/${animationId}`, { method: "PUT", body: JSON.stringify({ frame_rate: frameRate, loop: loopMode === "loop" || loopMode === "ping_pong", loop_mode: loopMode, loop_start_frame: loopStart, loop_end_frame: loopEnd, hold_first_frame_ms: holdFirst, hold_last_frame_ms: holdLast }) }); toast.success("Playback settings saved"); await load(); }
  async function validate() { const result = await api<ValidationResult>(`/api/sprite-animations/${animationId}/validate`, { method: "POST", body: "{}" }); setValidation(result); toast.success("Frame checks complete"); }
  async function approve() { try { await api(`/api/sprite-animations/${animationId}/approve`, { method: "POST", body: "{}" }); toast.success("Animation approved"); await load(); } catch (reason) { toast.error(reason instanceof Error ? reason.message : "Approval requirements are not complete"); } }
  async function applyDuration() { await Promise.all(selectedIds.map(id => api(`/api/sprite-frames/${id}`, { method: "PUT", body: JSON.stringify({ duration_ms: batchDuration }) }))); toast.success("Duration applied to selected frames"); await load(); }
  function select(id: string, additive: boolean) { setSelectedIds(values => additive ? values.includes(id) ? values.filter(value => value !== id) : [...values, id] : [id]); }
  if (error) return <ErrorState message={error}/>;
  if (!animation) return <LoadingState cards={5}/>;
  return <div className="space-y-7"><PageHeader eyebrow={`${animation.character?.name ?? "Asset"} · ${animation.category.replaceAll("_", " ")}`} title={animation.name} description={animation.description || "One reusable frame-by-frame motion state."} actions={<div className="flex flex-wrap gap-2"><Button asChild variant="ghost"><Link href="/sprite-studio"><ArrowLeft className="size-4"/>Library</Link></Button><Button asChild variant="outline"><Link href={`/art-review?mode=sprite&animation=${animation.id}`}><ScanSearch className="size-4"/>Sprite Review</Link></Button><Button asChild><Link href={`/motion-studio?source=sprite&animation=${animation.id}`}><Film className="size-4"/>Use in Motion Studio</Link></Button></div>}/><div className="flex flex-wrap gap-2"><Badge>{animation.status}</Badge><Badge>{animation.approval_level}</Badge><Badge>{animation.frame_count}/{animation.expected_frame_count} frames</Badge><Badge>{animation.loop_mode.replaceAll("_", " ")}</Badge>{animation.technical_sample && <Badge>Technical sample — never official</Badge>}</div><div className="grid gap-6 xl:grid-cols-[1.05fr_.95fr]"><div className="space-y-5"><Card><CardHeader><CardTitle>Loop preview</CardTitle></CardHeader><CardContent><SpritePreview frames={animation.frames.slice(loopStart, Math.min(animation.frames.length, loopEnd + 1))} frameRate={animation.frame_rate} loopMode={animation.loop_mode}/></CardContent></Card><Card><CardHeader><CardTitle>Frames</CardTitle></CardHeader><CardContent className="space-y-4">{animation.frames.length ? <FrameTimeline frames={animation.frames} selectedIds={selectedIds} onSelect={select} onReorder={reorder} onRemove={removeFrame} onDuplicate={duplicateFrame}/> : <p className="rounded-xl bg-wash p-6 text-center text-sm text-muted">Upload approved frames to bring this animation to life.</p>}{selectedIds.length > 0 && <div className="flex flex-wrap items-end gap-2"><div><Label>Selected duration</Label><Input className="w-28" type="number" min="16" value={batchDuration} onChange={event => setBatchDuration(Number(event.target.value))}/></div><Button type="button" variant="outline" onClick={applyDuration}>Apply to {selectedIds.length} selected</Button><Button type="button" variant="ghost" onClick={() => setLoopStart(Math.max(0, selectedIndex))}>Set loop start</Button><Button type="button" variant="ghost" onClick={() => setLoopEnd(Math.max(0, selectedIndex))}>Set loop end</Button></div>}</CardContent></Card><Card><CardHeader><CardTitle>Add frames</CardTitle></CardHeader><CardContent><Tabs defaultValue="frames"><TabsList><TabsTrigger value="frames">Individual frames</TabsTrigger><TabsTrigger value="sheet">Sprite sheet</TabsTrigger></TabsList><TabsContent value="frames" className="mt-4"><FrameDropzone onFiles={upload}/></TabsContent><TabsContent value="sheet" className="mt-4 space-y-4"><FrameDropzone onFiles={files => setSheet(files[0] ?? null)} multiple={false} label="Choose an existing sprite sheet"/><div className="grid grid-cols-2 gap-3 sm:grid-cols-4"><SmallField label="Frame width"><Input type="number" value={frameWidth} onChange={event => setFrameWidth(Number(event.target.value))}/></SmallField><SmallField label="Frame height"><Input type="number" value={frameHeight} onChange={event => setFrameHeight(Number(event.target.value))}/></SmallField><SmallField label="Rows"><Input type="number" min="1" value={rows} onChange={event => setRows(Number(event.target.value))}/></SmallField><SmallField label="Columns"><Input type="number" min="1" value={columns} onChange={event => setColumns(Number(event.target.value))}/></SmallField></div><SpriteSheetPreview file={sheet} frameWidth={frameWidth} frameHeight={frameHeight} rows={rows} columns={columns} selectedCells={selectedCells} onToggle={cell => setSelectedCells(values => values.includes(cell) ? values.filter(value => value !== cell) : [...values, cell])}/><label className="flex items-center gap-2 text-xs font-semibold"><input type="checkbox" checked={transparentBackground} onChange={event => setTransparentBackground(event.target.checked)}/> Require transparent background</label><Button type="button" onClick={importSheet} disabled={!sheet || !selectedCells.length}><UploadCloud className="size-4"/>Slice and import selected cells</Button></TabsContent></Tabs></CardContent></Card></div><div className="space-y-5"><Card><CardHeader><CardTitle>Selected frame</CardTitle></CardHeader><CardContent><FrameInspector frame={selectedFrame} onSave={changes => selectedFrame && updateFrame(selectedFrame.id, changes)}/></CardContent></Card><Card><CardHeader><CardTitle>Anchor and alignment</CardTitle></CardHeader><CardContent><AnchorPointEditor frame={selectedFrame} onChange={changes => selectedFrame && updateFrame(selectedFrame.id, changes)} onAlignSelected={() => align("selected_frame")} onAlignBottom={() => align("bottom_center")}/></CardContent></Card><OnionSkinPreview frames={animation.frames} selectedIndex={Math.max(0, selectedIndex)}/><Card><CardHeader><CardTitle>Loop settings</CardTitle></CardHeader><CardContent className="space-y-4"><LoopSettings loopMode={loopMode} onLoopMode={setLoopMode} frameRate={frameRate} onFrameRate={setFrameRate} loopStart={loopStart} loopEnd={loopEnd} frameCount={animation.frame_count} onLoopStart={setLoopStart} onLoopEnd={setLoopEnd} holdFirst={holdFirst} holdLast={holdLast} onHoldFirst={setHoldFirst} onHoldLast={setHoldLast}/><Button type="button" size="sm" variant="outline" onClick={saveLoop}><Check className="size-4"/>Save playback</Button></CardContent></Card><Card><CardHeader><CardTitle>Review and approval</CardTitle></CardHeader><CardContent><ValidationPanel animation={animation} validation={validation} onValidate={validate} onApprove={approve}/></CardContent></Card><div className="flex flex-wrap gap-2"><ExportDialog animation={animation}/><Button asChild variant="outline"><Link href="/sprite-studio/exports">Export history</Link></Button></div></div></div></div>;
}

function SmallField({ label, children }: { label: string; children: React.ReactNode }) { return <div className="space-y-1"><Label className="text-xs">{label}</Label>{children}</div>; }
