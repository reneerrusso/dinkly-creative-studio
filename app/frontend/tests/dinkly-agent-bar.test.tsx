import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DinklyAgentBar } from "@/components/dinkly-agent-bar";

const runtime = {
  state: "generating", status: "GENERATING", status_kind: "Active", message: "Creating DINKLY candidates.", last_event: "Candidate B started.",
  last_event_at: "2026-08-07T12:00:00Z", source_run_id: "generation-1", source_event_id: "event-1", details: {}, expires_at: null,
  updated_at: "2026-08-07T12:00:00Z", expression: { state: "generating", custom: false, path: "/agents/social-intelligence.png", fallback_path: "/agents/social-intelligence.png" },
};
const task = { id: "task-1", source_channel: "slack", source_thread_id: "slack-thread", user_instruction: "Generate PARTY / PARTY WITH YOU", task_type: "generate_comic", status: "running", priority: 1, context: {}, run_ids: ["generation-1"], artifact_ids: [], result: {}, error: null, created_at: "2026-08-07T12:00:00Z", started_at: "2026-08-07T12:00:01Z", completed_at: null };
const event = { id: "event-1", state: "generating", message: "Candidate B is generating.", source_run_id: "generation-1", source_event_id: null, details: { task_id: "task-1", stage: "generate", candidate: "B", completed: 2, total: 4 }, timestamp: "2026-08-07T12:00:02Z" };

describe("global DINKLY Agent bar", () => {
  beforeEach(() => vi.mocked(globalThis.fetch).mockImplementation(async input => {
    const url = String(input);
    if (url.includes("/api/dinkly-agent/workspace")) return { ok: true, json: async () => ({ agent: runtime, waiting: { concepts: 0, comics: 0, brain_updates: 0 }, recent_work: [], brain_updates: [], queued_tasks: 0, running_tasks: 1, current_task: task, current_run: null }) } as Response;
    if (url.includes("/api/dinkly-agent/events")) return { ok: true, json: async () => [event] } as Response;
    return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) } as Response;
  }));

  it("shows persisted Slack-triggered work and compact task details", async () => {
    const user = userEvent.setup();
    render(<DinklyAgentBar/>);
    expect(await screen.findByText("Generating Candidate B · 2 of 4")).toBeInTheDocument();
    expect(screen.getByText("Working")).toBeInTheDocument();
    expect(screen.getByAltText("DINKLY Agent")).toHaveClass("object-cover");
    await user.click(screen.getByRole("button", { name: "Open DINKLY Agent status" }));
    expect(screen.getByRole("region", { name: "DINKLY Agent status details" })).toHaveTextContent("Generate PARTY / PARTY WITH YOU");
    expect(screen.getByText("View Live Work")).toBeInTheDocument();
  });
});
