"use client";

import { useParams } from "next/navigation";

import { AgentRoom } from "@/components/agent-room";
import { ErrorState } from "@/components/error-state";
import { agentById } from "@/lib/agents";

export default function AgentPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const agent = agentById(agentId);
  if (!agent) return <ErrorState message="This specialist is not part of the DINKLY studio yet."/>;
  return <AgentRoom agent={agent}/>;
}
