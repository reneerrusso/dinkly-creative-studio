import * as React from "react";
import { cn } from "@/lib/utils";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => <select ref={ref} className={cn("h-10 w-full rounded-xl border border-line bg-white px-3 text-sm outline-none focus:border-ink/40", className)} {...props}>{children}</select>,
);
Select.displayName = "Select";
