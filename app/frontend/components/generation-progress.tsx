import { ModelPowerBadge } from "@/components/model-power-badge";
import type { GenerationEvent, GenerationRun } from "@/lib/types";

const stages = [
  { id: "story", label: "Story" },
  { id: "compile", label: "Compile" },
  { id: "references", label: "References" },
  { id: "generate", label: "Generate" },
  { id: "layout", label: "Layout" },
  { id: "qa", label: "QA" },
  { id: "repair", label: "Repair" },
  { id: "human_review", label: "Human Review" },
] as const;

type StageId = (typeof stages)[number]["id"];
type StageStatus = "pending" | "active" | "complete" | "warning" | "failed" | "skipped";

export function GenerationProgress({ run, events }: { run: GenerationRun; events: GenerationEvent[] }) {
  const progress = events.filter(event => event.kind === "progress" && event.data.stage);
  const latestByStage = new Map<StageId, GenerationEvent>();
  for (const event of progress) latestByStage.set(event.data.stage as StageId, event);
  const current = [...progress].reverse().find(event => event.data.status === "active") ?? progress.at(-1);
  const activeModel = current?.data.model ?? run.selected_model_info ?? undefined;
  const currentTask = current?.message ?? fallbackMessage(run);

  return <section aria-label="Generation progress" className="overflow-hidden rounded-[28px] border border-black/[0.07] bg-[#171713] text-[#f7f4ec] shadow-[0_28px_80px_-65px_rgba(0,0,0,.8)]">
    <div className="grid gap-5 border-b border-white/10 p-5 sm:grid-cols-[1fr_auto] sm:items-center sm:p-6">
      <div><div className="flex items-center gap-2"><p className="text-sm font-semibold">DINKLY Agent</p>{current?.data.status === "active" && <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-[.14em] text-[#e7c85d]">Working <WorkingDots /></span>}</div><p className="mt-1 text-[10px] uppercase tracking-[.16em] text-white/40">Current task</p><p aria-live="polite" className="mt-1 text-sm leading-5 text-white/75">{currentTask}</p></div>
      {activeModel && <ModelPowerBadge model={activeModel} inverse />}
    </div>
    <div className="grid gap-2 p-4 sm:p-5 lg:grid-cols-7">{stages.map(stage => <Stage key={stage.id} label={stage.label} event={latestByStage.get(stage.id)} />)}</div>
    {(run.status === "generating" || run.candidates.length > 0) && <div className="grid gap-4 border-t border-white/10 p-5 md:grid-cols-2">
      <CandidateProgress run={run} event={latestByStage.get("generate")} />
      <QaProgress run={run} event={latestByStage.get("qa")} />
    </div>}
    {latestByStage.has("repair") && latestByStage.get("repair")?.data.status !== "skipped" && <RepairProgress event={latestByStage.get("repair")!} />}
  </section>;
}

function Stage({ label, event }: { label: string; event?: GenerationEvent }) {
  const status = (event?.data.status ?? "pending") as StageStatus;
  return <div aria-label={`${label}: ${status}`} className={`relative min-h-[82px] overflow-hidden rounded-xl border px-3 py-3 ${tone(status)}`}><div className="flex items-center justify-between gap-2"><p className="text-[9px] font-black uppercase tracking-[.14em]">{label}</p><span aria-hidden="true" className="text-xs">{symbol(status)}</span></div><p className="mt-2 line-clamp-2 text-[10px] leading-4 opacity-70">{event?.message ?? "Waiting"}</p>{status === "active" && <div className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden bg-white/10"><span className="block h-full w-1/3 animate-[dinkly-progress_1.6s_ease-in-out_infinite] bg-[#e7c85d]" /></div>}</div>;
}

function CandidateProgress({ run, event }: { run: GenerationRun; event?: GenerationEvent }) {
  const slots = run.comparison ? run.comparison_model_info?.map(model => model.power_label) ?? [] : Array.from({ length: run.candidate_count }, (_, index) => String.fromCharCode(65 + index));
  const completed = run.candidates.filter(candidate => candidate.image_path).length;
  return <div><div className="flex items-center justify-between"><div><p className="text-[9px] font-bold uppercase tracking-[.15em] text-white/45">Generating candidates</p><p className="mt-1 text-xs text-white/75">{completed} / {run.candidate_count} successful</p></div></div><div className="mt-3 flex flex-wrap gap-2">{slots.map(label => { const candidate = run.candidates.find(item => item.label.split(" ")[0] === label || item.model_power_label === label); const working = event?.data.candidate === label && event.data.candidate_status === "working"; const status = candidate?.image_path ? "complete" : candidate?.error ? "failed" : working ? "working" : "waiting"; return <span key={label} aria-label={`Candidate ${label}: ${status}`} className={`rounded-lg border px-2.5 py-1.5 text-[10px] font-semibold ${status === "complete" ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-200" : status === "failed" ? "border-red-400/25 bg-red-400/10 text-red-200" : status === "working" ? "border-[#e7c85d]/35 bg-[#e7c85d]/10 text-[#f3db86]" : "border-white/10 text-white/35"}`}>{label} {status === "complete" ? "✓" : status === "failed" ? "Failed" : status === "working" ? "Working…" : "Waiting"}</span>; })}</div></div>;
}

function QaProgress({ run, event }: { run: GenerationRun; event?: GenerationEvent }) {
  const generated = run.candidates.filter(candidate => candidate.image_path);
  const checked = generated.filter(candidate => candidate.qa_status !== "Pending").length;
  return <div><p className="text-[9px] font-bold uppercase tracking-[.15em] text-white/45">QA</p><p className="mt-1 text-xs text-white/75">{checked} / {generated.length || run.candidate_count} checked</p><div className="mt-3 flex flex-wrap gap-2">{generated.map(candidate => { const working = event?.data.candidate === candidate.label && event.data.candidate_status === "working"; const status = working ? "checking" : candidate.qa_status === "Pending" ? "waiting" : candidate.qa_status; return <span key={candidate.id} aria-label={`Candidate ${candidate.label} QA: ${status}`} className="rounded-lg border border-white/10 px-2.5 py-1.5 text-[10px] text-white/65">{candidate.label} {working ? "Checking…" : candidate.qa_status === "Pending" ? "Waiting" : candidate.qa_status}</span>; })}</div></div>;
}

function RepairProgress({ event }: { event: GenerationEvent }) {
  const step = String(event.data.repair_step ?? event.data.status ?? "waiting").replaceAll("_", " ");
  return <div className="border-t border-white/10 p-5"><p className="text-[9px] font-bold uppercase tracking-[.15em] text-white/45">Repair progress</p><div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-white/70"><span>{event.message}</span>{event.data.issue && <span><strong className="text-white/45">Issue:</strong> {String(event.data.issue)}</span>}<span className="capitalize"><strong className="text-white/45">Step:</strong> {step}</span></div></div>;
}

function WorkingDots() { return <span aria-hidden="true" className="inline-flex gap-0.5"><i className="size-1 animate-pulse rounded-full bg-current" /><i className="size-1 animate-pulse rounded-full bg-current [animation-delay:180ms]" /><i className="size-1 animate-pulse rounded-full bg-current [animation-delay:360ms]" /></span>; }
function symbol(status: StageStatus) { return status === "complete" ? "✓" : status === "active" ? "•••" : status === "warning" ? "!" : status === "failed" ? "×" : status === "skipped" ? "–" : "○"; }
function tone(status: StageStatus) { return status === "complete" ? "border-emerald-400/20 bg-emerald-400/[.07] text-emerald-100" : status === "active" ? "border-[#e7c85d]/35 bg-[#e7c85d]/[.08] text-[#f3db86]" : status === "warning" ? "border-amber-400/30 bg-amber-400/[.07] text-amber-100" : status === "failed" ? "border-red-400/30 bg-red-400/[.08] text-red-100" : "border-white/[.08] text-white/35"; }
function fallbackMessage(run: GenerationRun) { return run.status === "approved" ? "Comic approved and ready to download." : run.status === "awaiting_human" ? "Ready for your approval." : "Preparing the next production step…"; }
