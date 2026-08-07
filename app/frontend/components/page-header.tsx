import type { ReactNode } from "react";
export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="flex flex-col gap-4 border-b border-line pb-6 sm:flex-row sm:items-end sm:justify-between"><div className="max-w-2xl">{eyebrow && <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-mustard-dark">{eyebrow}</p>}<h1 className="text-3xl font-semibold tracking-[-0.035em] text-ink sm:text-4xl">{title}</h1><p className="mt-2 text-sm leading-6 text-muted sm:text-base">{description}</p></div>{actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}</div>;
}
