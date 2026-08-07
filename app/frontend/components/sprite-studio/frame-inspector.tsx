"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { SpriteFrame } from "@/lib/types";

export function FrameInspector({ frame, onSave }: { frame?: SpriteFrame; onSave: (changes: Partial<SpriteFrame>) => void }) {
  if (!frame) return <div className="rounded-xl bg-wash p-4 text-sm text-muted">Select a frame to adjust duration and review status.</div>;
  return <div className="space-y-4" data-testid="frame-inspector"><div className="grid grid-cols-2 gap-3"><Field label="Duration (ms)"><Input type="number" min="16" defaultValue={frame.duration_ms} onBlur={event => onSave({ duration_ms: Number(event.target.value) })}/></Field><Field label="Opacity"><Input type="number" min="0" max="1" step="0.05" defaultValue={frame.opacity} onBlur={event => onSave({ opacity: Number(event.target.value) })}/></Field></div><Field label="Frame review"><Select value={frame.review_status} onChange={event => onSave({ review_status: event.target.value as SpriteFrame["review_status"], approved: event.target.value === "Pass" })}><option>Not reviewed</option><option>Pass</option><option>Needs edit</option><option>Reject</option></Select></Field><Field label="Review notes"><Textarea defaultValue={frame.review_notes} onBlur={event => onSave({ review_notes: event.target.value })} placeholder="Record the exact frame-level issue or approval note."/></Field><div className="rounded-xl bg-wash p-3 text-xs"><p><strong>{frame.width}×{frame.height}px</strong> · anchor {frame.anchor_x.toFixed(2)}, {frame.anchor_y.toFixed(2)}</p>{frame.validation_warnings.length ? <ul className="mt-2 space-y-1 text-orange-700">{frame.validation_warnings.map(item => <li key={item}>• {item}</li>)}</ul> : <p className="mt-1 text-emerald-700">Automatic checks passed.</p>}</div><Button type="button" size="sm" variant="outline" onClick={() => onSave({ review_status: "Pass", approved: true })}>Mark frame passed</Button></div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <div className="space-y-1.5"><Label>{label}</Label>{children}</div>; }

