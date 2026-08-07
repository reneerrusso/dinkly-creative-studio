"use client";

import Link from "next/link";
import { Bot, CheckCircle2, ChevronLeft, ChevronRight, Clock3, Menu, Settings } from "lucide-react";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { brainNavigation } from "@/lib/agents";
import { cn } from "@/lib/utils";

const primary = [
  { label: "DINKLY Agent", href: "/agent", icon: Bot },
  { label: "Approvals", href: "/approvals", icon: CheckCircle2 },
  { label: "History", href: "/history", icon: Clock3 },
];

function Brand({ collapsed = false }: { collapsed?: boolean }) {
  return <Link href="/agent" aria-label="DINKLY Agent home" className={cn("flex items-center rounded-xl py-1", collapsed ? "justify-center" : "gap-3 px-1")}>
    <span aria-hidden="true" className="flex size-9 items-center justify-center rounded-xl border border-black/[0.06] bg-[#f2df9d] text-sm font-black">D</span>
    {!collapsed && <div><p className="text-[13px] font-black tracking-[-0.02em]">DINKLY</p><p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-muted">Agent workspace</p></div>}
  </Link>;
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <span className="block px-2 text-[9px] font-bold uppercase tracking-[0.2em] text-[#99958b]">{children}</span>;
}

function Navigation({ onNavigate, collapsed = false }: { onNavigate?: () => void; collapsed?: boolean }) {
  const pathname = usePathname();
  const [brainOpen, setBrainOpen] = useState(!["/", "/agent", "/approvals", "/comics", "/history", "/settings"].some(path => pathname === path || (path !== "/" && pathname.startsWith(`${path}/`))));
  return <div className="flex min-h-0 flex-1 flex-col">
    <nav aria-label="DINKLY Agent" className="mt-8 space-y-1">
      {primary.map(item => { const Icon = item.icon; const active = pathname.startsWith(item.href); return <Link key={item.href} href={item.href} onClick={onNavigate} title={collapsed ? item.label : undefined} className={cn("flex min-h-11 items-center rounded-xl py-2 text-[13px] font-semibold transition-colors", collapsed ? "justify-center px-1" : "gap-3 px-3", active ? "bg-[#f2df9d] text-ink" : "text-[#5f5b54] hover:bg-black/[0.035]")}><Icon className="size-4" />{!collapsed && item.label}</Link>; })}
    </nav>
    {!collapsed && <div className="mt-8">
      <button type="button" aria-expanded={brainOpen} onClick={() => setBrainOpen(value => !value)} className="flex w-full items-center justify-between rounded-lg px-2 py-1 text-left hover:bg-black/[0.025]">
        <SectionLabel>Brain</SectionLabel><ChevronRight className={cn("size-3 text-[#99958b] transition-transform", brainOpen && "rotate-90")} />
      </button>
      {brainOpen && <nav aria-label="DINKLY Brain" className="mt-2 space-y-0.5 pl-1">{brainNavigation.map(item => { const Icon = item.icon; const base = item.href.split("?")[0]; const active = pathname === base; return <Link key={item.label} href={item.href} onClick={onNavigate} className={cn("flex h-8 items-center gap-2.5 rounded-lg px-2 text-[11px] font-medium transition-colors", active ? "bg-black/[0.055] text-ink" : "text-[#77736b] hover:bg-black/[0.035]")}><Icon className="size-3.5" />{item.label}</Link>; })}</nav>}
    </div>}
    <div className="mt-auto pt-8">
      <Link href="/settings" onClick={onNavigate} title={collapsed ? "Settings" : undefined} className={cn("flex h-10 items-center rounded-xl text-[12px] font-semibold transition-colors", collapsed ? "justify-center" : "gap-3 px-3", pathname === "/settings" ? "bg-black/[0.055]" : "text-[#77736b] hover:bg-black/[0.035]")}><Settings className="size-4" />{!collapsed && "Settings"}</Link>
    </div>
  </div>;
}

export function AppSidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  return <>
    <aside data-testid="desktop-sidebar" className={cn("fixed inset-y-0 left-0 z-40 hidden border-r border-black/[0.055] bg-[#fbfaf6] transition-[width] duration-200 lg:block", collapsed ? "w-[76px]" : "w-[276px]")}>
      <div className={cn("flex h-full flex-col py-5", collapsed ? "px-2" : "px-4")}><div className="flex items-center justify-between"><Brand collapsed={collapsed} /><Button type="button" variant="ghost" size="icon" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={() => setCollapsed(value => !value)} className={cn("size-8", collapsed && "absolute right-[-16px] top-5 border bg-white shadow-sm")}>{collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}</Button></div><Navigation collapsed={collapsed} /></div>
    </aside>
    <div className={cn("hidden shrink-0 transition-[width] duration-200 lg:block", collapsed ? "w-[76px]" : "w-[276px]")} />
    <div className="lg:hidden"><Dialog open={mobileOpen} onOpenChange={setMobileOpen}><DialogTrigger asChild><Button aria-label="Open DINKLY Agent navigation" variant="ghost" size="icon" className="fixed left-3 top-2.5 z-50 bg-white/90 shadow-sm"><Menu className="size-5" /></Button></DialogTrigger><DialogContent className="left-0 top-0 h-screen max-h-none w-[294px] max-w-none translate-x-0 translate-y-0 rounded-none border-y-0 border-l-0 bg-[#fbfaf6] p-5"><div className="flex h-full flex-col"><Brand /><Navigation onNavigate={() => setMobileOpen(false)} /></div></DialogContent></Dialog></div>
  </>;
}
