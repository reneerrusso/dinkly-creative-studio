import { ModelPowerBadge } from "@/components/model-power-badge";
import { Select } from "@/components/ui/select";
import type { ImageModelInfo } from "@/lib/types";

type SelectionMode = "automatic" | "lite" | "balanced" | "pro";

interface ImageModelSelectorProps {
  value: SelectionMode;
  models: ImageModelInfo[];
  selectedForRun?: ImageModelInfo | null;
  selectionReason?: string;
  onChange: (value: SelectionMode) => void;
}

export function ImageModelSelector({ value, models, selectedForRun, selectionReason, onChange }: ImageModelSelectorProps) {
  return <section className="space-y-3" aria-label="Image model selection">
    <div className="space-y-1.5"><label htmlFor="generation-model" className="text-xs font-medium">Model</label><Select id="generation-model" value={value} onChange={event => onChange(event.target.value as SelectionMode)}><option value="automatic">Automatic</option>{models.map(model => <option key={model.id} value={model.selection_mode}>{model.power_label} · {model.display_name}</option>)}</Select></div>
    {value === "automatic" && selectedForRun && <div className="rounded-xl border border-[#b99a48]/25 bg-[#fff9e7] p-3"><p className="text-[9px] font-bold uppercase tracking-[.16em] text-[#8b6a18]">Selected for this run</p><div className="mt-2"><ModelPowerBadge model={selectedForRun} /></div>{selectionReason && <p className="mt-2 text-[11px] leading-5 text-muted"><strong>Reason:</strong> {selectionReason}</p>}</div>}
    <div className="grid gap-2 sm:grid-cols-3">{models.map(model => <button key={model.id} type="button" onClick={() => model.selection_mode && onChange(model.selection_mode)} aria-pressed={value === model.selection_mode} className={`rounded-xl border p-3 text-left transition ${value === model.selection_mode ? "border-[#a7832b] bg-[#fff9e7] shadow-sm" : "border-line bg-white hover:border-black/20"}`}><ModelPowerBadge model={model} compact /><p className="mt-3 text-xs font-semibold">{model.display_name}</p><p className="mt-1 min-h-10 text-[10px] leading-4 text-muted">{model.description}</p><p className="mt-2 text-[9px] font-bold uppercase tracking-wider text-muted">Best for</p><ul className="mt-1 space-y-0.5 text-[10px] leading-4 text-muted">{model.recommended_for.slice(0, 4).map(item => <li key={item}>• {item}</li>)}</ul>{model.power_level === 2 && <p className="mt-2 text-[9px] font-bold uppercase tracking-wider text-emerald-700">Recommended</p>}{model.power_level === 3 && <p className="mt-2 text-[9px] font-bold uppercase tracking-wider text-amber-800">Higher cost</p>}</button>)}</div>
  </section>;
}
