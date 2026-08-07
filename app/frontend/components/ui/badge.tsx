import * as React from "react";
import { cn } from "@/lib/utils";

export function Badge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("inline-flex items-center rounded-full bg-wash px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-muted", className)} {...props} />;
}
