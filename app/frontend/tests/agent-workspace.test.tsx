import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AgentPage from "@/app/agent/page";

const workspace = {
  agent: {
    state: "idle", status: "ONLINE", status_kind: "Idle", message: "Ready when you are.", last_event: "Ready when you are.",
    last_event_at: "2026-08-07T12:00:00Z", source_run_id: null, source_event_id: null, details: {}, expires_at: null,
    updated_at: "2026-08-07T12:00:00Z", expression: { state: "idle", custom: false, path: "/agents/social-intelligence.png", fallback_path: "/agents/social-intelligence.png" },
  },
  waiting: { concepts: 0, comics: 0, brain_updates: 0 }, recent_work: [], brain_updates: [], queued_tasks: 0, running_tasks: 0,
};

const walks = {
  id: "story-everyday-routines-walks", title: "Walks", title_left: "WALKS", title_right: "WALKS WITH YOU",
  concept: "An ordinary walk becomes companionship.", category: "Everyday routines", format: "x-with-you", approved: true,
};

describe("DINKLY Agent workspace", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads the Story Library and sends the selected story id into the same Agent inbox", async () => {
    const user = userEvent.setup();
    vi.mocked(globalThis.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/dinkly-agent/workspace")) return { ok: true, json: async () => workspace } as Response;
      if (url.includes("/api/dinkly-agent/conversations")) return { ok: true, json: async () => [] } as Response;
      if (url.endsWith("/api/story-library")) return { ok: true, json: async () => [walks] } as Response;
      if (url.endsWith("/api/dinkly-agent/instructions") && init?.method === "POST") {
        return { ok: true, json: async () => ({ task: activeTask, reply: "Queued" }) } as Response;
      }
      return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) } as Response;
    });

    render(<AgentPage />);
    const selector = await screen.findByRole("combobox", { name: "Choose from Story Library" });
    await user.selectOptions(selector, walks.id);
    await user.click(screen.getByRole("button", { name: "Build Story" }));

    await waitFor(() => {
      const call = vi.mocked(globalThis.fetch).mock.calls.find(([input]) => String(input).endsWith("/api/dinkly-agent/instructions"));
      expect(call).toBeDefined();
      const body = JSON.parse(String(call?.[1]?.body));
      expect(body.message).toBe("Generate WALKS / WALKS WITH YOU.");
      expect(body.context.story_id).toBe(walks.id);
    });
  });

  it("keeps the Story Library visible and offers an explicit retry after a load failure", async () => {
    vi.mocked(globalThis.fetch).mockImplementation(async input => {
      const url = String(input);
      if (url.endsWith("/api/dinkly-agent/workspace")) return { ok: true, json: async () => workspace } as Response;
      if (url.includes("/api/dinkly-agent/conversations")) return { ok: true, json: async () => [] } as Response;
      if (url.endsWith("/api/story-library")) return { ok: false, status: 503, json: async () => ({ detail: "Story Library unavailable" }) } as Response;
      return { ok: true, json: async () => ({}) } as Response;
    });

    render(<AgentPage />);

    expect(await screen.findByText("Story Library unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry Story Library" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Choose from Story Library" })).toBeInTheDocument();
  });

  it("restores a persisted running task after navigation instead of showing Idle", async () => {
    vi.mocked(globalThis.fetch).mockImplementation(async input => {
      const url = String(input);
      if (url.endsWith("/api/dinkly-agent/workspace")) return { ok: true, json: async () => ({ ...workspace, agent: { ...workspace.agent, state: "generating", status: "GENERATING" }, current_task: activeTask, current_run: activeRun, running_tasks: 1 }) } as Response;
      if (url.includes("/api/dinkly-agent/conversations")) return { ok: true, json: async () => [] } as Response;
      if (url.endsWith("/api/story-library")) return { ok: true, json: async () => [walks] } as Response;
      return { ok: true, json: async () => [] } as Response;
    });

    render(<AgentPage/>);

    expect(await screen.findByRole("region", { name: "Active task progress" })).toHaveTextContent("Generate WALKS / WALKS WITH YOU");
    expect(screen.getByRole("heading", { name: "Current Work" })).toBeInTheDocument();
    expect(screen.queryByAltText("DINKLY Agent portrait")).not.toBeInTheDocument();
  });
});

const activeTask = { id: "task-1", source_channel: "web", source_thread_id: "web-default", user_instruction: "Generate WALKS / WALKS WITH YOU", task_type: "generate_comic", status: "running", priority: 1, context: { story_id: walks.id }, run_ids: ["generation-1"], artifact_ids: [], result: {}, error: null, created_at: "2026-08-07T12:00:00Z", started_at: "2026-08-07T12:00:01Z", completed_at: null };
const activeRun = { id: "generation-1", concept_text: "WALKS / WALKS WITH YOU", candidate_count: 4, candidates: [], status: "generating", comparison: false };
