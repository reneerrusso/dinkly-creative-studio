"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import { AGENT_ASSET_VERSION, agentById } from "@/lib/agents";
import { cn } from "@/lib/utils";

const sizes = {
  xs: "size-8",
  sm: "size-9",
  md: "size-12",
  lg: "size-20",
  xl: "size-28 sm:size-32",
};

const imageSizes = { xs: "32px", sm: "36px", md: "48px", lg: "80px", xl: "128px" };

type AgentStatus = "online" | "working" | "offline";

export function AgentAvatar({
  agentId,
  size = "md",
  className,
  status = "online",
  showStatus = false,
  priority = false,
}: {
  agentId: string;
  size?: keyof typeof sizes;
  className?: string;
  status?: AgentStatus;
  showStatus?: boolean;
  priority?: boolean;
}) {
  const agent = agentById(agentId);
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [agentId, agent?.avatarPath]);

  const displayName = agent?.displayName ?? agentId.replaceAll("-", " ");
  const initials = displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(word => word[0]?.toUpperCase())
    .join("") || "D";

  return <span data-agent-id={agent?.id ?? agentId} data-testid={`agent-avatar-${agent?.id ?? agentId}`} className={cn("relative inline-flex shrink-0 overflow-visible", sizes[size], className)}>
    <span className="relative size-full overflow-hidden rounded-[28%] border border-black/[0.06] bg-[#f4efe4]">
      {agent && !failed ? <Image
        src={`${agent.avatarPath}?v=${AGENT_ASSET_VERSION}`}
        alt={`${agent.displayName} DINKLY agent`}
        fill
        priority={priority}
        unoptimized
        sizes={imageSizes[size]}
        onError={() => setFailed(true)}
        className="object-contain"
      /> : <span role="img" aria-label={`${displayName} DINKLY agent portrait unavailable`} className="flex size-full items-center justify-center bg-[#ede7da] text-[.7em] font-black tracking-[-0.04em] text-[#686158]">{initials}</span>}
    </span>
    {showStatus && <span aria-label={`${status} status`} className={cn(
      "absolute -bottom-0.5 -right-0.5 size-3 rounded-full border-2 border-white",
      status === "working" ? "bg-amber-500" : status === "offline" ? "bg-neutral-400" : "bg-emerald-500",
    )}/>} 
  </span>;
}
