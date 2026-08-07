"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import type { DinklyAgentVisualState } from "@/lib/types";
import { cn } from "@/lib/utils";

const sizes = {
  xs: { frame: "size-9", pixels: "36px" },
  sm: { frame: "size-11", pixels: "44px" },
  md: { frame: "size-14", pixels: "56px" },
  lg: { frame: "size-20", pixels: "80px" },
  xl: { frame: "size-44", pixels: "176px" },
  hero: { frame: "size-full", pixels: "320px" },
};

const presentation: Record<DinklyAgentVisualState, { status: string; kind: "Idle" | "Active" | "Waiting" | "Warning"; expression: string }> = {
  idle: { status: "ONLINE", kind: "Idle", expression: "idle" },
  learning: { status: "LEARNING", kind: "Active", expression: "learning" },
  preparing: { status: "PREPARING", kind: "Active", expression: "idle" },
  generating: { status: "GENERATING", kind: "Active", expression: "generating" },
  reviewing: { status: "REVIEWING", kind: "Active", expression: "reviewing" },
  repairing: { status: "FIXING", kind: "Active", expression: "repairing" },
  waiting_for_human: { status: "WAITING FOR YOU", kind: "Waiting", expression: "waiting" },
  success: { status: "DONE", kind: "Idle", expression: "success" },
  error: { status: "NEEDS ATTENTION", kind: "Warning", expression: "error" },
};

export function DinklyAgentStatus({
  state,
  message,
  lastEvent,
  size = "sm",
  compact = false,
  showLiveIndicator = true,
  expressionPath,
  className,
  portraitOnly = false,
}: {
  state: DinklyAgentVisualState;
  message?: string;
  lastEvent?: string | null;
  size?: keyof typeof sizes;
  compact?: boolean;
  showLiveIndicator?: boolean;
  expressionPath?: string;
  className?: string;
  portraitOnly?: boolean;
}) {
  const current = presentation[state];
  const fallback = "/agents/social-intelligence.png";
  const initial = expressionPath ?? `/agents/dinkly-agent/${current.expression}.png`;
  const [source, setSource] = useState(initial);
  useEffect(() => setSource(initial), [initial]);

  if (portraitOnly) return <div data-agent-state={state} className={cn("relative shrink-0", sizes[size].frame, className)}>
    <span className={cn("relative block size-full overflow-hidden rounded-[28%] border border-black/[0.06] bg-[#f4efe4]", `dinkly-agent-motion-${state}`)}>
      <Image src={source} alt="DINKLY Agent portrait" fill unoptimized sizes={sizes[size].pixels} onError={() => { if (source !== fallback) setSource(fallback); }} className="object-contain p-[7.5%]" />
    </span>
  </div>;

  return <div data-agent-state={state} aria-live={state === "idle" ? "off" : "polite"} className={cn("flex min-w-0 items-center gap-2.5", className)}>
    <span className={cn("relative shrink-0", sizes[size].frame, `dinkly-agent-motion-${state}`)}>
      <span className="relative block size-full overflow-hidden rounded-[28%] border border-black/[0.06] bg-[#f4efe4]">
        <Image src={source} alt="Social Intelligence DINKLY agent" fill unoptimized sizes={sizes[size].pixels} onError={() => { if (source !== fallback) setSource(fallback); }} className="object-contain" />
      </span>
    </span>
    <div className="min-w-0">
      {!compact && <p className="truncate text-[11px] font-semibold text-[#5f5b54]">DINKLY Agent</p>}
      <div className="flex items-center gap-1.5">
        {showLiveIndicator && <span aria-hidden="true" className={cn("size-1.5 shrink-0 rounded-full", current.kind === "Active" ? "bg-amber-500" : current.kind === "Waiting" ? "bg-sky-500" : current.kind === "Warning" ? "bg-red-500" : "bg-emerald-500")} />}
        <span className="truncate text-[9px] font-black tracking-[.12em] text-[#6e665d]">{current.status}</span>
        {showLiveIndicator && <span className="sr-only">{current.kind} status.</span>}
      </div>
      {!compact && <p className="mt-0.5 max-w-[260px] truncate text-[10px] text-muted">{message ?? lastEvent ?? defaultMessage(state)}</p>}
    </div>
  </div>;
}

function defaultMessage(state: DinklyAgentVisualState) {
  return ({
    idle: "Ready when you are.",
    learning: "Reviewing new production evidence.",
    preparing: "Building the story brief.",
    generating: "Creating DINKLY candidates.",
    reviewing: "Checking character consistency.",
    repairing: "Applying a targeted repair.",
    waiting_for_human: "A candidate is ready for approval.",
    success: "Comic approved.",
    error: "The current task needs attention.",
  } satisfies Record<DinklyAgentVisualState, string>)[state];
}
