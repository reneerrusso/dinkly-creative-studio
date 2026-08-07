import { comicModel, comicStatus, comicThumbnail, filterComics } from "@/lib/comics";
import type { GenerationRun } from "@/lib/types";

function run(status: GenerationRun["status"] = "awaiting_human"): GenerationRun {
  return {
    id: "generation-1", concept_id: null, concept_text: "RAIN / RAIN WITH YOU", story_format: "x-with-you", status,
    source_channel: "slack", source_task_id: "task-1", model_selection_mode: "balanced", selected_model: null,
    selection_reason: "", candidate_count: 1, selected_candidate_id: null, final_asset_url: null, started_at: "2026-08-07T12:00:00Z",
    completed_at: null, approved_at: null, runtime_ms: null, estimated_cost: null, reported_cost: null, warnings: [], error: null, comparison: false,
    story_brief: { format: "x-with-you", title_left: "RAIN", title_right: "RAIN WITH YOU", left_character: "boy", left_action: "Dinko waits in rain.", left_setting: "street", left_props: ["umbrella"], left_emotion: "neutral", right_characters: ["boy", "girl"], right_action: "Dinko and Dinka share an umbrella.", right_setting: "street", right_props: ["umbrella"], right_emotion: "warm", shared_environment: "rainy street", environmental_contrast: "shared", background_color: "powder blue", accent_color: "coral", camera_angle: "straight-on", execution_risks: [], emotional_insight: "Rain is warmer together.", brand_sensitive: false },
    candidates: [{ id: "candidate-a", label: "A", image_path: "image.png", asset_url: "/generation-assets/original.png", final_asset_url: "/generation-assets/final.png", model: "balanced", model_display_name: "Nano Banana 2", model_power_label: "BALANCED", model_power_level: 2, model_description: "", model_cost_tier: "", runtime_ms: 1000, qa_status: "Pass", qa_summary: "Passed", qa_findings: [], rank: 1, recommended: true, selected: false, repair_parent_id: null, estimated_cost: null, reported_cost: null }],
    prompt_record: { prompt_id: "prompt-1", template: "SplitComic", template_version: "1", character_rule_version: "1", failure_rule_version: "1", created_at: "2026-08-07T12:00:00Z" },
  };
}

describe("comic library helpers", () => {
  it("maps persisted generation states to human gallery states", () => {
    expect(comicStatus(run("awaiting_human"))).toBe("Waiting for Approval");
    expect(comicStatus(run("approved"))).toBe("Approved");
    expect(comicStatus(run("rejected"))).toBe("Passed");
    expect(comicStatus(run("generating"))).toBe("Draft");
  });

  it("uses the recommended final 80/20 image and model", () => {
    expect(comicThumbnail(run())).toContain("/generation-assets/final.png");
    expect(comicModel(run())).toBe("BALANCED · Nano Banana 2");
  });

  it("filters by storyline and status without creating a second history", () => {
    expect(filterComics([run(), { ...run("approved"), id: "generation-2", concept_text: "COFFEE / COFFEE WITH YOU" }], "coffee", "All")).toHaveLength(1);
    expect(filterComics([run(), run("approved")], "", "Approved")).toHaveLength(1);
  });
});
