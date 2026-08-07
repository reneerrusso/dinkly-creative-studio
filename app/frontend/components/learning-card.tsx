import type { Learning } from "@/lib/types";
import { EvidenceList } from "@/components/evidence-list";
import { StatusPill } from "@/components/status-pill";
import { Card, CardContent } from "@/components/ui/card";

export function LearningCard({ learning }: { learning: Learning }) {
  return <Card><CardContent className="p-6"><div className="flex items-center justify-between gap-2"><StatusPill status={learning.confidence}/><span className="text-xs text-muted">Updated {learning.last_updated || "date missing"}</span></div><div className="mt-4 space-y-4"><Section label="Observed pattern"><h3 className="font-semibold leading-6">{learning.pattern}</h3></Section><Section label="Measured basis"><p className="text-sm text-muted">{learning.metric_supported ? "Supported by recorded performance metrics." : "Visual or editorial observation; not metric-supported."}</p><div className="mt-2"><EvidenceList ids={learning.evidence_post_ids}/></div></Section><Section label="Hypothesis"><p className="text-sm leading-6 text-muted">{learning.hypothesis}</p></Section><Section label="Recommendation"><p className="border-l-2 border-mustard pl-3 text-sm leading-6">{learning.recommended_use}</p></Section><Section label="Do not overgeneralize"><p className="text-xs leading-5 text-muted">{learning.avoid_overgeneralizing}</p></Section></div></CardContent></Card>;
}
function Section({ label, children }: { label: string; children: React.ReactNode }) { return <div><p className="mb-1.5 text-[10px] font-bold uppercase tracking-[.14em] text-muted">{label}</p>{children}</div>; }
