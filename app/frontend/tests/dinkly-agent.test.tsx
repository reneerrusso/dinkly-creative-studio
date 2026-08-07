import { render, screen } from "@testing-library/react";

import { DinklyAgentStatus } from "@/components/dinkly-agent-status";

describe("truthful DINKLY Agent visual states", () => {
  it.each([
    ["idle", "ONLINE"],
    ["learning", "LEARNING"],
    ["preparing", "PREPARING"],
    ["generating", "GENERATING"],
    ["reviewing", "REVIEWING"],
    ["repairing", "FIXING"],
    ["waiting_for_human", "WAITING FOR YOU"],
    ["success", "DONE"],
    ["error", "NEEDS ATTENTION"],
  ] as const)("renders %s state", (state, label) => {
    render(<DinklyAgentStatus state={state} message="Real backend activity." />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByText("Real backend activity.")).toBeInTheDocument();
  });

  it("uses the canonical Social Intelligence portrait as its fallback", () => {
    render(<DinklyAgentStatus state="idle" expressionPath="/agents/social-intelligence.png" />);
    expect(screen.getByAltText("Social Intelligence DINKLY agent")).toHaveAttribute("src", expect.stringContaining("social-intelligence.png"));
  });
});

