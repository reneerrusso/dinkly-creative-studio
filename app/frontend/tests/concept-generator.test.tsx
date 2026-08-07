import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ConceptGeneratorPage from "@/app/agents/concept-generator/page";
import { AppSidebar } from "@/components/app-sidebar";

function concept(format: "with_you" | "before_after" | "five_story", index: number) {
  const five = format === "five_story";
  return {
    id: `${format}-${index}`, batch_id: "batch-today", format, status: "candidate", slot: index,
    title_left: five ? undefined : `TITLE ${index}`, title_right: five ? undefined : `TITLE ${index} WITH YOU`, story_title: five ? `STORY ${index}` : undefined,
    left_action: "Dinko waits beside a rounded table and two chairs.", left_setting: "home", left_props: ["table", "chair"],
    right_action: "Dinko and Dinka share the same routine beside the table.", right_setting: "home", right_props: ["table", "two chairs"],
    background_color: "warm cream", accent_color: "muted mustard", emotional_insight: "Together changes the feeling.", emotional_premise: "Five small moments build toward belonging.",
    why_it_may_work: "A familiar situation has a clear emotional contrast.", timely_signal: null, preference_matches: [], social_learning_ids: [], execution_risks: ["Keep anatomy simple."],
    comics: five ? Array.from({ length: 5 }, (_, beat) => ({ title: `Comic ${beat + 1}`, scene: `Simple connected scene ${beat + 1}.`, setting: "home", props: ["chair"], emotion: "warm" })) : [],
    final_payoff: five ? "Ordinary life became ours." : undefined, prompt_ids: [], development_fixture: true,
  };
}

const batch = { id: "batch-today", date: "2026-08-06", status: "waiting_for_review", source_summary: "Clearly labeled development fixtures.", with_you_count: 10, before_after_count: 10, five_story_count: 10, approved_count: 0, used_count: 0 };
const allConcepts = (["with_you", "before_after", "five_story"] as const).flatMap(format => Array.from({ length: 10 }, (_, index) => concept(format, index + 1)));

function state(overrides: Record<string, unknown> = {}) {
  return { provider_configured: true, provider_name: "development-fixtures", today: "2026-08-06", today_batches: [batch], batches: [batch], today_concepts: allConcepts, production_queue: [], passed: [], used_storylines: [], preferences: [], chat: [], settings: { generate_daily_automatically: false, run_time: "08:00", timezone: "America/New_York", schedule_days: "every_day", catch_up_on_wake: true, catch_up_on_start: true, generate_on_start: false, enable_paid_model_calls: false, maximum_automatic_batch_cost: 1, maximum_manual_batch_cost: 5, daily_model_budget: 5, monthly_model_budget: 25, last_scheduler_check: null }, scheduler: { last_successful_run: "2026-08-06T12:42:00Z", next_run: "2026-08-07T08:00:00-04:00", last_status: "Succeeded", last_run_id: "run-1" }, background_agent: { installed: true, running: true, status: "Running" }, latest_run: { id: "run-1", status: "Completed", kind: "concept-generator-daily-batch", created_at: "2026-08-06T12:42:00Z" }, ...overrides };
}

describe("Concept Generator", () => {
  beforeEach(() => vi.clearAllMocks());

  it("remains available as an internal room but is hidden behind the one-agent navigation", () => {
    render(<AppSidebar/>);
    expect(screen.queryByText("Concept Generator")).not.toBeInTheDocument();
    expect(screen.getAllByText("DINKLY Agent").length).toBeGreaterThan(0);
    expect(screen.queryByText("Content Agent")).not.toBeInTheDocument();
  });

  it("shows ten concepts in one format at a time and records approval", async () => {
    const user = userEvent.setup();
    let current = state();
    vi.mocked(globalThis.fetch).mockImplementation(async input => {
      const url = String(input);
      if (url.endsWith("/api/concept-generator")) return { ok: true, json: async () => current } as Response;
      if (url.includes("/approve")) {
        current = { ...current, today_concepts: (current.today_concepts as any[]).filter(item => item.id !== "with_you-1"), production_queue: [concept("with_you", 1)] };
        return { ok: true, json: async () => ({ status: "approved" }) } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    });
    render(<ConceptGeneratorPage/>);
    expect(await screen.findAllByRole("article")).toHaveLength(10);
    await user.click(screen.getByRole("button", { name: /BEFORE \/ AFTER 10/ }));
    expect(screen.getAllByRole("article")).toHaveLength(10);
    await user.click(screen.getByRole("button", { name: /WITH YOU 10/ }));
    await user.click(screen.getAllByRole("button", { name: "Approve" })[0]);
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/approve"), expect.objectContaining({ method: "POST" })));
  });

  it("stores chat feedback and shows an honest missing-provider state", async () => {
    const user = userEvent.setup();
    let offline = false;
    vi.mocked(globalThis.fetch).mockImplementation(async input => {
      const url = String(input);
      if (url.endsWith("/api/concept-generator") && offline) return { ok: true, json: async () => state({ provider_configured: false, today_batches: [], batches: [], today_concepts: [], latest_run: undefined }) } as Response;
      if (url.endsWith("/api/concept-generator")) return { ok: true, json: async () => state() } as Response;
      if (url.endsWith("/chat")) { offline = true; return { ok: true, json: async () => ({ reply: { message: "I’ll reduce couch scenes." }, preference: { preference_type: "less_of" } }) } as Response; }
      return { ok: true, json: async () => ({}) } as Response;
    });
    render(<ConceptGeneratorPage/>);
    const input = await screen.findByPlaceholderText("Tell Concept Generator what you want more or less of…");
    await user.type(input, "Less couch scenes");
    await user.click(screen.getByRole("button", { name: "Send feedback" }));
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/chat"), expect.objectContaining({ method: "POST" })));
    expect(await screen.findByText("Concept Generator needs an AI provider to create new concepts.")).toBeInTheDocument();
  });
});
