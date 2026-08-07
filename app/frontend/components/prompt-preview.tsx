"use client";

import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

interface PromptSection { title: string; content: string }

export function PromptPreview({ prompt, rules = [], sections = [] }: { prompt: string; rules?: string[]; sections?: PromptSection[] }) {
  const [copied, setCopied] = useState(false);
  const normalizedPrompt = prompt.replaceAll("\\n", "\n");
  async function copy(value = normalizedPrompt, label = "Prompt") { await navigator.clipboard.writeText(value.replaceAll("\\n", "\n")); setCopied(true); toast.success(`${label} copied`); window.setTimeout(() => setCopied(false), 1400); }
  function download() { const blob = new Blob([normalizedPrompt], { type: "text/markdown" }); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "dinkly-nano-banana-prompt.md"; link.click(); URL.revokeObjectURL(url); }
  return <div className="rounded-2xl border border-line bg-[#171713] text-[#f7f4ec]"><div className="flex items-center justify-between border-b border-white/10 px-4 py-3"><p className="text-xs font-semibold uppercase tracking-widest text-white/55">Production prompt</p><div className="flex gap-1"><Button aria-label="Copy prompt" variant="ghost" size="sm" className="text-white hover:bg-white/10" onClick={() => copy()}>{copied ? <Check className="size-4"/> : <Copy className="size-4"/>} Copy all</Button><Button aria-label="Download prompt" variant="ghost" size="icon" className="text-white hover:bg-white/10" onClick={download}><Download className="size-4"/></Button></div></div>{sections.length ? <div className="divide-y divide-white/10">{sections.map((section, index) => <details key={section.title} open={index < 2}><summary className="flex cursor-pointer list-none items-center justify-between px-5 py-4 text-xs font-semibold uppercase tracking-wider text-white/65"><span>{section.title}</span><Button aria-label={`Copy ${section.title}`} variant="ghost" size="icon" className="size-7 text-white/60 hover:bg-white/10" onClick={event => { event.preventDefault(); void copy(`## ${section.title}\n${section.content}`, section.title); }}><Copy className="size-3.5"/></Button></summary><pre className="whitespace-pre-wrap px-5 pb-5 font-sans text-sm leading-7 text-white/90">{section.content}</pre></details>)}</div> : <pre className="max-h-[60vh] whitespace-pre-wrap p-5 font-sans text-sm leading-7 text-white/90">{prompt || "Choose a saved concept or create a new one here. The production-ready prompt will appear here."}</pre>}{rules.length > 0 && <div className="border-t border-white/10 px-5 py-4"><p className="text-[11px] font-semibold uppercase tracking-wider text-white/45">Rules included for this scene</p><ul className="mt-2 space-y-1 text-xs text-white/65">{rules.map(rule => <li key={rule}>• {rule}</li>)}</ul></div>}</div>;
}
