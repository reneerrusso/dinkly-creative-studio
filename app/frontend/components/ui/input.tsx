import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => <input ref={ref} className={cn("h-10 w-full rounded-xl border border-line bg-white px-3 text-sm outline-none transition focus:border-ink/40 focus:ring-2 focus:ring-ink/5 disabled:bg-wash", className)} {...props} />,
);
Input.displayName = "Input";
