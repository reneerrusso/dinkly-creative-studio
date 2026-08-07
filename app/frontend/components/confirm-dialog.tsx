"use client";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
export function ConfirmDialog({ trigger, title, description, onConfirm }: { trigger: React.ReactNode; title: string; description: string; onConfirm: () => void }) { return <Dialog><DialogTrigger asChild>{trigger}</DialogTrigger><DialogContent><DialogHeader><DialogTitle className="text-lg font-semibold">{title}</DialogTitle><DialogDescription className="mt-2 text-sm leading-6 text-muted">{description}</DialogDescription></DialogHeader><div className="flex justify-end"><Button onClick={onConfirm}>Confirm</Button></div></DialogContent></Dialog>; }
