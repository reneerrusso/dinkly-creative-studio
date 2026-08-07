"use client";

import { AlertTriangle, CheckCircle2, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { SpriteAnimation } from "@/lib/types";

export function ValidationPanel({ animation, validation, onValidate, onApprove }: { animation: SpriteAnimation; validation?: { status: string; issues: Array<{ frame_id: string | null; issue: string; severity: string }>; checklist: string[]; blocking: boolean }; onValidate: () => void; onApprove: () => void }) {
  const checklist = validation?.checklist ?? animation.validation_checklist ?? [];
  return <div className="space-y-4" data-testid="sprite-validation"><div className="flex items-start gap-3 rounded-xl bg-wash p-4"><ShieldCheck className="mt-0.5 size-5"/><div><p className="text-sm font-semibold">Character-consistency review</p><p className="mt-1 text-xs leading-5 text-muted">Automatic checks cover files, transparency, dimensions, anchors, and drift. A person must approve character identity.</p></div></div>{validation?.issues.length ? <div className="space-y-2">{validation.issues.map((issue, index) => <div key={`${issue.frame_id}-${index}`} className="flex gap-2 rounded-lg border border-orange-200 bg-orange-50 p-3 text-xs text-orange-800"><AlertTriangle className="size-4 shrink-0"/><span>{issue.frame_id ? `Frame ${issue.frame_id}: ` : ""}{issue.issue}</span></div>)}</div> : validation ? <div className="flex gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800"><CheckCircle2 className="size-4"/>Structural frame checks passed.</div> : null}<div className="grid gap-1.5 sm:grid-cols-2">{checklist.map(item => <label key={item} className="flex gap-2 rounded-lg border border-line p-2.5 text-xs"><input type="checkbox"/> {item}</label>)}</div><div className="flex flex-wrap gap-2"><Button type="button" variant="outline" onClick={onValidate}>Run frame checks</Button><Button type="button" onClick={onApprove} disabled={!animation.frame_count || Boolean(validation?.blocking)}>Approve animation</Button></div>{animation.technical_sample && <p className="text-xs font-semibold text-orange-700">Technical samples can never be approved as official DINKLY assets.</p>}</div>;
}

