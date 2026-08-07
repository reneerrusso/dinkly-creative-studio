import type { ImageModelInfo } from "@/lib/types";

interface ModelPowerBadgeProps {
  model: Partial<Pick<ImageModelInfo, "display_name" | "power_label" | "power_level">>;
  compact?: boolean;
  inverse?: boolean;
}

export function ModelPowerBadge({ model, compact = false, inverse = false }: ModelPowerBadgeProps) {
  const powerLabel = model.power_label ?? "MODEL";
  const displayName = model.display_name ?? "Image model";
  const powerLevel = model.power_level ?? 0;
  return <div aria-label={`Power level: ${titleCase(powerLabel)}. ${displayName}.`} className={`inline-flex items-center gap-2 rounded-xl border px-2.5 py-2 ${inverse ? "border-white/15 bg-white/10 text-white" : "border-black/[0.07] bg-white text-ink"}`}>
    <div><p className="text-[9px] font-black tracking-[.16em]">{powerLabel}</p>{!compact && <p className={`mt-0.5 text-[10px] font-semibold ${inverse ? "text-white/65" : "text-muted"}`}>{displayName}</p>}</div>
    <span aria-hidden="true" className="flex gap-1">{[1, 2, 3].map(level => <span key={level} className={`size-1.5 rounded-full ${level <= powerLevel ? inverse ? "bg-[#f0cc5b]" : "bg-[#8b6a18]" : inverse ? "bg-white/20" : "bg-black/10"}`} />)}</span>
  </div>;
}

function titleCase(value: string) {
  return value.charAt(0) + value.slice(1).toLowerCase();
}
