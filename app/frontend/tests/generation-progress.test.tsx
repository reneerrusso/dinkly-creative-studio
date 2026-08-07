import { render, screen } from "@testing-library/react";

import { GenerationProgress } from "@/components/generation-progress";
import { ModelPowerBadge } from "@/components/model-power-badge";
import type { GenerationEvent, GenerationRun } from "@/lib/types";

describe("Generation Engine progress and model power", () => {
  it.each([
    ["FAST", 1, "Nano Banana 2 Lite"],
    ["BALANCED", 2, "Nano Banana 2"],
    ["MAX", 3, "Nano Banana Pro"],
  ] as const)("renders the %s model tier accessibly", (powerLabel, powerLevel, displayName) => {
    render(<ModelPowerBadge model={{ power_label: powerLabel, power_level: powerLevel, display_name: displayName }} />);
    expect(screen.getByLabelText(new RegExp(`Power level: ${powerLabel}`, "i"))).toHaveTextContent(displayName);
  });

  it("does not crash when a legacy record has no power metadata", () => {
    render(<ModelPowerBadge model={{}} />);
    expect(screen.getByLabelText(/Power level: Model/i)).toHaveTextContent("Image model");
  });

  it("reconstructs stage state from persisted progress events", () => {
    const run = {
      id: "generation-123456789abc",
      status: "generating",
      candidate_count: 4,
      candidates: [],
      comparison: false,
      selected_model_info: {
        id: "nano_banana_2",
        display_name: "Nano Banana 2",
        power_label: "BALANCED",
        power_level: 2,
        description: "Two-character production model.",
        recommended_for: [],
        cost_tier: "standard",
      },
    } as unknown as GenerationRun;
    const events = [
      progress("story", "complete", "Story Brief ready."),
      progress("compile", "complete", "Production prompt compiled."),
      progress("references", "complete", "Official character references loaded."),
      progress("generate", "active", "Generating Candidate A with Nano Banana 2."),
    ];
    render(<GenerationProgress run={run} events={events} />);
    expect(screen.getByLabelText("Story: complete")).toBeInTheDocument();
    expect(screen.getByLabelText("Generate: active")).toBeInTheDocument();
    expect(screen.getAllByText("Generating Candidate A with Nano Banana 2.").length).toBeGreaterThan(0);
  });
});

function progress(stage: GenerationEvent["data"]["stage"], status: GenerationEvent["data"]["status"], message: string): GenerationEvent {
  return { id: `${stage}-${status}`, run_id: "generation-123456789abc", timestamp: "2026-08-07T12:00:00Z", level: "info", kind: "progress", message, data: { stage, status } };
}
