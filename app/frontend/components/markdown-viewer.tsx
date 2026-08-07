import type { ReactNode } from "react";

export function MarkdownViewer({ content }: { content: string }) {
  const blocks: ReactNode[] = [];
  let inCode = false;
  let code: string[] = [];

  content.split("\n").forEach((line, index) => {
    if (line.startsWith("```")) {
      if (inCode) { blocks.push(<pre key={`code-${index}`} className="overflow-auto rounded-xl bg-ink p-4 font-mono text-xs leading-6 text-white"><code>{code.join("\n")}</code></pre>); code = []; }
      inCode = !inCode;
      return;
    }
    if (inCode) { code.push(line); return; }
    if (!line.trim()) { blocks.push(<div key={index} className="h-3"/>); return; }
    if (line.startsWith("### ")) { blocks.push(<h3 key={index}>{line.slice(4)}</h3>); return; }
    if (line.startsWith("## ")) { blocks.push(<h2 key={index}>{line.slice(3)}</h2>); return; }
    if (line.startsWith("# ")) { blocks.push(<h1 key={index}>{line.slice(2)}</h1>); return; }
    if (line.startsWith("- ")) { blocks.push(<div key={index} className="flex gap-2 text-sm leading-6"><span>•</span><span>{line.slice(2)}</span></div>); return; }
    if (/^\d+\.\s/.test(line)) { blocks.push(<div key={index} className="pl-4 text-sm leading-6">{line}</div>); return; }
    if (line.startsWith("|")) { blocks.push(<pre key={index} className="overflow-x-auto border-b border-line py-2 font-mono text-xs">{line}</pre>); return; }
    if (line.startsWith("> ")) { blocks.push(<blockquote key={index} className="border-l-2 border-mustard pl-4 text-sm italic text-muted">{line.slice(2)}</blockquote>); return; }
    blocks.push(<p key={index} className="text-sm leading-7 text-ink/85">{line}</p>);
  });

  return <article className="prose prose-neutral max-w-none prose-headings:tracking-tight prose-table:text-sm">{blocks}</article>;
}
