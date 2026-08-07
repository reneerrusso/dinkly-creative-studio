import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AgentTaskProgress } from "@/components/agent-task-progress";
import type { AgentTask, DinklyAgentActivity, GenerationRun } from "@/lib/types";

describe("persisted Agent task progress", () => {
  it("shows real candidate, layout, QA, and approval progress", () => {
    const task = baseTask({ status: "waiting_for_human", run_ids: ["generation-1"] });
    const run = { concept_text: "COFFEE / COFFEE WITH YOU", candidate_count: 4, candidates: [{ image_path: "a" }, { image_path: "b" }], status: "awaiting_human" } as unknown as GenerationRun;
    const events = [event("story", "complete", "Story ready"), event("compile", "complete", "Prompt compiled"), event("references", "complete", "References loaded"), event("generate", "complete", "Candidate B received", { candidate: "B", completed: 2, total: 4 }), event("layout", "complete", "Layout applied"), event("qa", "complete", "QA complete")];
    render(<AgentTaskProgress task={task} run={run} events={events} onRetry={vi.fn()} onReview={vi.fn()}/>);
    expect(screen.getByLabelText("Generating 2 / 4: complete")).toBeInTheDocument();
    expect(screen.getByLabelText("Applying DINKLY layout: complete")).toBeInTheDocument();
    expect(screen.getByLabelText("QA: complete")).toBeInTheDocument();
    expect(screen.getByLabelText("Waiting for approval: active")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review Comic" })).toBeInTheDocument();
  });

  it("restores completed stages from the persisted awaiting-human run state", () => {
    const task = baseTask({ status: "waiting_for_human", run_ids: ["generation-1"] });
    const run = { concept_text: "PARTY / PARTY WITH YOU", candidate_count: 4, candidates: [{ image_path: "a" }, { image_path: "b" }, { image_path: "c" }, { image_path: "d" }], status: "awaiting_human", completed_at: "2026-08-07T12:01:00Z" } as unknown as GenerationRun;

    render(<AgentTaskProgress task={task} run={run} events={[event("qa", "active", "Stale QA event")]} onRetry={vi.fn()} onReview={vi.fn()}/>);

    for (const label of ["Story brief", "Prompt compiled", "References loaded", "Generating 4 / 4", "Applying DINKLY layout", "QA"]) {
      expect(screen.getByLabelText(`${label}: complete`)).toBeInTheDocument();
    }
    expect(screen.getByLabelText("Waiting for approval: active")).toBeInTheDocument();
    expect(screen.getAllByText("The strongest candidate is ready for approval.").length).toBeGreaterThan(0);
  });

  it("ends the loader on failure and offers a retry", async () => {
    const retry = vi.fn(); const user = userEvent.setup();
    render(<AgentTaskProgress task={baseTask({ status: "failed", error: "Candidate C timed out" })} run={null} events={[event("generate", "failed", "Candidate C failed", { candidate: "C" })]} onRetry={retry} onReview={vi.fn()}/>);
    expect(screen.getByRole("region", { name: "Task failed" })).toHaveTextContent("Candidate C timed out");
    expect(screen.queryByLabelText("Working")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("shows a truthful stopping state after cancellation is requested", () => {
    render(<AgentTaskProgress task={baseTask({ status: "cancellation_requested" })} run={null} events={[event("generate", "active", "Candidate B provider call is in flight", { candidate: "B", completed: 1, total: 4 })]} onRetry={vi.fn()} onReview={vi.fn()}/>);
    expect(screen.getByText("DINKLY Agent · STOPPING")).toBeInTheDocument();
    expect(screen.getAllByText("Finishing the current safe step…").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Cancel Task" })).not.toBeInTheDocument();
  });

  it("transitions to a terminal cancelled state without a working loader", () => {
    render(<AgentTaskProgress task={baseTask({ status: "cancelled", completed_at: "2026-08-07T12:00:05Z" })} run={null} events={[]} onRetry={vi.fn()} onReview={vi.fn()}/>);
    expect(screen.getByRole("region", { name: "Task cancelled" })).toHaveTextContent("stopped safely");
    expect(screen.queryByLabelText("Working")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Restart Task" })).toBeInTheDocument();
  });
});

function baseTask(changes: Partial<AgentTask>): AgentTask { return { id: "task-1", source_channel: "web", source_thread_id: "web-default", user_instruction: "Generate COFFEE / COFFEE WITH YOU", task_type: "generate_comic", status: "running", priority: 1, context: {}, run_ids: [], artifact_ids: [], result: {}, error: null, created_at: "2026-08-07T12:00:00Z", started_at: "2026-08-07T12:00:01Z", completed_at: null, ...changes }; }
function event(stage: string, status: string, message: string, details: Record<string, unknown> = {}): DinklyAgentActivity { return { id: `${stage}-${status}`, state: stage === "qa" ? "reviewing" : "generating", message, source_run_id: "generation-1", source_event_id: null, details: { stage, status, ...details }, timestamp: "2026-08-07T12:00:02Z" } as DinklyAgentActivity; }
