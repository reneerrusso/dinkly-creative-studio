import type { SpriteAnimation } from "@/lib/types";
import { Select } from "@/components/ui/select";

export function AnimationStateSelector({ animations, value, onChange, approvedOnly = false, label = "Choose animation" }: { animations: SpriteAnimation[]; value: string; onChange: (value: string) => void; approvedOnly?: boolean; label?: string }) {
  const options = approvedOnly ? animations.filter(item => item.approved) : animations;
  return <Select aria-label={label} value={value} onChange={event => onChange(event.target.value)}><option value="">{options.length ? label : approvedOnly ? "No approved animations" : "No animations available"}</option>{options.map(animation => <option key={animation.id} value={animation.id}>{animation.character?.name ?? "Asset"} · {animation.name}{animation.approved ? "" : " — Draft"}</option>)}</Select>;
}

