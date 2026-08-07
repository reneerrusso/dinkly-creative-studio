import * as React from "react";
import { cn } from "@/lib/utils";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => <textarea ref={ref} className={cn("min-h-28 w-full resize-y rounded-xl border border-line bg-white px-3 py-2.5 text-sm leading-6 outline-none transition focus:border-ink/40 focus:ring-2 focus:ring-ink/5", className)} {...props} />,
);
Textarea.displayName = "Textarea";
