import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ApprovalsPage from "@/app/approvals/page";
import type { AgentApprovals, GenerationRun } from "@/lib/types";

const run = {
  id: "generation-123456789abc", concept_text: "COFFEE / COFFEE WITH YOU", status: "awaiting_human", model_selection_mode: "balanced", selected_model: "nano_banana_2", selection_reason: "Two-character consistency", candidate_count: 2, selected_candidate_id: null, final_asset_url: null, started_at: "2026-08-07T12:00:00Z", completed_at: "2026-08-07T12:01:30Z", approved_at: null, runtime_ms: 90000, estimated_cost: 0.1, reported_cost: null, warnings: [], error: null, comparison: false,
  story_format: "x-with-you", concept_id: "coffee", story_brief: { format: "x-with-you", title_left: "COFFEE", title_right: "COFFEE WITH YOU", left_character: "boy", left_action: "Dinko sits alone.", left_setting: "Cafe", left_props: ["mug"], left_emotion: "neutral", right_characters: ["boy", "girl"], right_action: "They share coffee.", right_setting: "Cafe", right_props: ["mugs"], right_emotion: "warm", shared_environment: "Cafe", environmental_contrast: "Together", background_color: "cream", accent_color: "sage", camera_angle: "straight-on", execution_risks: [], emotional_insight: "Better together", brand_sensitive: false },
  candidates: [candidate("A", "candidate-a", false), candidate("B", "candidate-b", true)],
  prompt_record: { prompt_id: "prompt-1", template: "SplitComic", template_version: "1", character_rule_version: "1", failure_rule_version: "1", created_at: "2026-08-07T12:00:00Z" },
} as unknown as GenerationRun;

const approvals: AgentApprovals = {
  comics: [run],
  concepts: [{ id: "concept-1", format: "with_you", title_left: "WALKS", title_right: "WALKS WITH YOU", left_action: "Dinko walks alone.", right_action: "Dinko and Dinka walk together.", left_props: ["bench"], right_props: ["bench", "flowers"], background_color: "mint", accent_color: "sage", why_it_may_work: "A familiar ritual", social_learning_ids: ["learning-1"], preference_matches: ["small routines"] }],
  brain_updates: [{ id: "learning-1", learning_type: "qa_pattern", statement: "Simple shared routines improve clarity.", evidence_ids: ["generation-1"], confidence: "high", status: "proposed", created_at: "2026-08-07T12:00:00Z", updated_at: "2026-08-07T12:00:00Z" }],
};

describe("approval review modal", () => {
  beforeEach(() => vi.mocked(globalThis.fetch).mockImplementation(async input => {
    const url = String(input);
    if (url.endsWith("/api/dinkly-agent/approvals")) return { ok: true, json: async () => approvals } as Response;
    if (url.includes("/select")) return { ok: true, json: async () => run } as Response;
    return { ok: true, json: async () => ({ task: { id: "task-approval" } }) } as Response;
  }));

  it("opens full comic detail, switches candidates, and exposes download", async () => {
    const user = userEvent.setup(); render(<ApprovalsPage/>);
    await user.click(await screen.findByRole("button", { name: "Review comic" }));
    expect(screen.getByText("Story brief")).toBeInTheDocument();
    expect(screen.getByText("Character consistency")).toBeInTheDocument();
    expect(screen.getByText("Prompt alignment")).toBeInTheDocument();
    expect(screen.getByText("WAITING FOR APPROVAL")).toBeInTheDocument();
    expect(screen.getByText("View full QA details")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve Comic" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Candidate A" }));
    expect(screen.getByAltText("Candidate A")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download/i })).toBeInTheDocument();
  });

  it("shows full concept and Brain update context without navigating away", async () => {
    const user = userEvent.setup(); render(<ApprovalsPage/>);
    await user.click(await screen.findByRole("button", { name: "Review details" }));
    expect(screen.getByText("Left scene")).toBeInTheDocument();
    expect(screen.getByText("Relevant learning / preference signals")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close" }));
    await user.click(screen.getByRole("button", { name: "Review evidence" }));
    expect(screen.getByText("Memory affected")).toBeInTheDocument();
    expect(screen.getByText("data/qa_learnings.json")).toBeInTheDocument();
  });
});

function candidate(label: string, id: string, recommended: boolean) { return { id, label, image_path: `/tmp/${id}.jpg`, asset_url: `/generation-assets/${id}.jpg`, model: "nano_banana_2", model_display_name: "Nano Banana 2", model_power_label: "BALANCED", model_power_level: 2, model_description: "Production model", model_cost_tier: "standard", runtime_ms: 10000, qa_status: "Pass", qa_summary: "All checks passed.", qa_findings: [{ category: "CHARACTER", check: "Dinko hair", status: "Pass", detail: "Two tufts." }, { category: "SCENE", check: "Cafe", status: "Pass", detail: "Accurate." }, { category: "TEXT", check: "Captions", status: "Pass", detail: "Exact." }], rank: recommended ? 1 : 2, recommended, selected: false, repair_parent_id: null, estimated_cost: 0.05, reported_cost: null, error: null }; }
