"use client";

import { FileText } from "lucide-react";
import { useEffect, useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface PromptTemplate {
  slug: string;
  title: string;
  path: string;
  content: string;
}

export default function PromptTemplatesPage() {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [active, setActive] = useState<PromptTemplate>();

  useEffect(() => {
    api<PromptTemplate[]>("/api/prompt-templates")
      .then(items => {
        setTemplates(items);
        setActive(items[0]);
      })
      .catch(() => setTemplates([]));
  }, []);

  return <div className="space-y-7">
    <PageHeader eyebrow="The Brain" title="Prompt templates" description="The modular production structures the Prompt Engineer uses to keep each Nano Banana brief concise and scene-specific."/>
    <div className="grid gap-5 lg:grid-cols-[270px_1fr]">
      <Card className="h-fit border-black/[0.055] shadow-none">
        <CardContent className="space-y-1 p-2">
          {templates.map(template => <button key={template.slug} type="button" onClick={() => setActive(template)} className={cn("w-full rounded-xl px-3 py-3 text-left text-sm font-semibold transition hover:bg-wash", active?.slug === template.slug && "bg-mustard")}>{template.title}<span className="mt-1 block text-[10px] font-normal text-muted">{template.path}</span></button>)}
        </CardContent>
      </Card>
      <Card className="border-black/[0.055] shadow-none">
        <CardContent className="p-6 lg:p-8">
          {active ? <MarkdownViewer content={active.content}/> : <EmptyState icon={FileText} title="No prompt templates found" description="Add production templates under PROMPT_TEMPLATES/."/>}
        </CardContent>
      </Card>
    </div>
  </div>;
}
