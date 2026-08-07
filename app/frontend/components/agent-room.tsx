"use client";

import Link from "next/link";
import { ArrowRight, Check, Clock3, MessageCircle, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { AgentAvatar } from "@/components/agent-avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { AgentDefinition } from "@/lib/agents";
import { api, getConcepts, getDashboard, getLearnings, getSpriteAnimations } from "@/lib/api";
import type { Concept, DashboardData, Learning, SpriteAnimation } from "@/lib/types";

interface RecentItem { title: string; detail: string; href: string }
interface AgentData {
  dashboard?: DashboardData;
  concepts: Concept[];
  learnings: Learning[];
  prompts: Array<Record<string, unknown>>;
  reviews: Array<Record<string, unknown>>;
  animations: SpriteAnimation[];
}

const emptyData: AgentData = { concepts: [], learnings: [], prompts: [], reviews: [], animations: [] };

export function AgentRoom({ agent }: { agent: AgentDefinition }) {
  const [data, setData] = useState<AgentData>(emptyData);
  useEffect(() => {
    Promise.all([
      getDashboard().catch(() => undefined),
      getConcepts().catch(() => []),
      getLearnings().catch(() => []),
      api<Array<Record<string, unknown>>>("/api/prompts").catch(() => []),
      api<Array<Record<string, unknown>>>("/api/art-reviews").catch(() => []),
      getSpriteAnimations().catch(() => []),
    ]).then(([dashboard, concepts, learnings, prompts, reviews, animations]) => setData({ dashboard, concepts, learnings, prompts, reviews, animations }));
  }, []);
  const recent = useMemo(() => recentWork(agent, data), [agent, data]);

  return <div className="mx-auto max-w-6xl space-y-8 pb-10 pt-3">
    <section className="relative overflow-hidden rounded-[28px] border border-black/[0.055] bg-white px-6 py-7 shadow-[0_24px_70px_-55px_rgba(30,27,20,.45)] sm:px-9 sm:py-9">
      <div className="absolute inset-y-0 left-0 w-1.5" style={{ backgroundColor: agent.statusColor }}/>
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <AgentAvatar agentId={agent.id} size="xl" priority showStatus className="ring-8 ring-white"/>
        <div className="max-w-2xl"><div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[.18em] text-muted"><span className="size-2 rounded-full bg-emerald-500"/>In the studio</div><h1 className="mt-3 text-4xl font-semibold tracking-[-.045em] sm:text-5xl">{agent.displayName}</h1><p className="mt-3 text-lg leading-7 text-[#6d675e]">{agent.personality}</p></div>
      </div>
      <div className="mt-7 rounded-2xl p-5 sm:ml-[152px]" style={{ backgroundColor: agent.accentSoft }}><div className="flex gap-3"><MessageCircle className="mt-0.5 size-4 shrink-0" style={{ color: agent.statusColor }}/><div><p className="text-[10px] font-bold uppercase tracking-[.16em]" style={{ color: agent.statusColor }}>A note from {agent.displayName}</p><p className="mt-2 max-w-3xl text-sm leading-6 text-[#4f4a43]">{agent.note}</p></div></div></div>
    </section>
    <section className="grid gap-5 lg:grid-cols-[1.15fr_.85fr]">
      <div className="space-y-5">
        <Card className="border-black/[0.055] shadow-none"><CardContent className="p-6 sm:p-7"><div className="flex items-center gap-2"><Clock3 className="size-4 text-muted"/><p className="text-[10px] font-bold uppercase tracking-[.17em] text-muted">Current objective</p></div><p className="mt-4 max-w-2xl text-xl font-semibold leading-8 tracking-[-.02em]">{agent.objective}</p><div className="mt-6 grid gap-2 sm:grid-cols-3">{agent.watchlist.map(item => <div key={item} className="flex items-center gap-2 rounded-xl bg-[#f7f5ef] px-3 py-3 text-xs font-semibold"><Check className="size-3.5" style={{ color: agent.statusColor }}/>{item}</div>)}</div></CardContent></Card>
        <Card className="border-black/[0.055] shadow-none"><CardContent className="p-6 sm:p-7"><p className="text-[10px] font-bold uppercase tracking-[.17em] text-muted">Recent work</p><div className="mt-4 divide-y divide-black/[0.06]">{recent.length ? recent.map(item => <Link key={`${item.title}-${item.href}`} href={item.href} className="group flex items-center justify-between gap-5 py-4 first:pt-0 last:pb-0"><div><p className="text-sm font-semibold group-hover:underline">{item.title}</p><p className="mt-1 text-xs leading-5 text-muted">{item.detail}</p></div><ArrowRight className="size-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5"/></Link>) : <p className="py-5 text-sm leading-6 text-muted">No recent work yet. Use a quick action to give this agent their first assignment.</p>}</div></CardContent></Card>
      </div>
      <div className="space-y-5">
        <Card className="border-black/[0.055] shadow-none"><CardContent className="p-6"><p className="text-[10px] font-bold uppercase tracking-[.17em] text-muted">Quick actions</p><div className="mt-4 space-y-2">{agent.actions.map(action => <Button key={action.label} asChild variant={action.primary ? "default" : "outline"} className="h-11 w-full justify-between"><Link href={action.href}><span>{action.label}</span><ArrowRight className="size-3.5"/></Link></Button>)}</div></CardContent></Card>
        <Card className="border-black/[0.055] shadow-none"><CardContent className="p-6"><div className="flex items-center gap-2"><Sparkles className="size-4" style={{ color: agent.statusColor }}/><p className="text-[10px] font-bold uppercase tracking-[.17em] text-muted">Suggestions</p></div><div className="mt-4 space-y-3">{agent.suggestions.map((item, index) => <div key={item} className="flex gap-3 text-sm leading-6"><span className="mt-0.5 font-mono text-[10px] text-muted">0{index + 1}</span><p>{item}</p></div>)}</div></CardContent></Card>
      </div>
    </section>
  </div>;
}

function recentWork(agent: AgentDefinition, data: AgentData): RecentItem[] {
  if (agent.id === "creative-director") {
    const learning = data.dashboard?.strongest_learnings[0];
    return [
      ...(learning ? [{ title: learning.pattern, detail: `${learning.confidence} confidence creative learning`, href: "/social-learning" }] : []),
      ...data.concepts.slice(0, 2).map(item => ({ title: `${item.title_pair.left} / ${item.title_pair.right}`, detail: item.emotional_insight || "Concept ready for direction", href: "/concepts" })),
    ];
  }
  if (agent.id === "prompt-agent") return data.prompts.slice(0, 3).map(item => ({ title: String(item.title ?? item.id ?? "Saved prompt"), detail: `${String(item.status ?? "draft")} prompt`, href: "/prompt-builder" }));
  if (agent.id === "art-review") return data.reviews.slice(-3).reverse().map(item => ({ title: String(item.recommendation ?? "Artwork review"), detail: String(item.reason ?? "Character consistency review"), href: "/art-review" }));
  if (agent.id === "social-intelligence") {
    const posts = data.dashboard?.performance.top_by_views ?? [];
    return posts.slice(0, 3).map(post => ({ title: post.title, detail: `${new Intl.NumberFormat("en", { notation: "compact" }).format(Number(post.views ?? 0))} measured views`, href: "/social-learning" }));
  }
  if (agent.id === "brand-integration") return data.concepts.filter(item => item.brand_friendly).slice(0, 3).map(item => ({ title: `${item.title_pair.left} / ${item.title_pair.right}`, detail: item.natural_product_placement || "Natural product opportunity recorded", href: "/brand-integrations" }));
  if (agent.id === "motion-director") return data.animations.filter(item => item.frame_count > 0).slice(0, 3).map(item => ({ title: `${item.character?.name ?? "Asset"} · ${item.name}`, detail: `${item.frame_count} frames · ${item.approval_level}`, href: `/sprite-studio/animations/${item.id}` }));
  return data.concepts.slice(0, 3).map(item => ({ title: `${item.title_pair.left} / ${item.title_pair.right}`, detail: item.emotional_insight || "Fresh concept", href: "/concepts" }));
}
