"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import type { AgentTask } from "@/lib/types";

export function TaskCancelControls({ task, allowSkip = false, onUpdated }: { task: AgentTask; allowSkip?: boolean; onUpdated?: () => void }) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function cancel(skip: boolean) {
    setSubmitting(true);
    try {
      const response = await api<{ task: AgentTask; message: string }>(`/api/dinkly-agent/tasks/${task.id}/${skip ? "skip" : "cancel"}`, { method: "POST" });
      toast.success(response.message);
      setOpen(false);
      onUpdated?.();
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not cancel task"); }
    finally { setSubmitting(false); }
  }

  if (task.status === "cancellation_requested") return <span className="text-[10px] font-black uppercase tracking-[.14em] text-[#8c6325]">STOPPING</span>;
  if (task.status !== "running") return null;
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button type="button" variant="outline" size="sm">Cancel Task</Button></DialogTrigger>
    <DialogContent className="max-w-sm">
      <DialogHeader><DialogTitle className="text-xl font-semibold">Cancel this task?</DialogTitle><DialogDescription className="pt-2 text-sm leading-6">Any completed work will be preserved. The next queued task will start automatically.</DialogDescription></DialogHeader>
      <div className="flex flex-wrap justify-end gap-2"><DialogClose asChild><Button type="button" variant="outline">Keep Running</Button></DialogClose>{allowSkip && <Button type="button" variant="outline" disabled={submitting} onClick={() => void cancel(true)}>Skip &amp; Start Next</Button>}<Button type="button" disabled={submitting} onClick={() => void cancel(false)}>Cancel Task</Button></div>
    </DialogContent>
  </Dialog>;
}
