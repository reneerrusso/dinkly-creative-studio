import { fireEvent, render, screen } from "@testing-library/react";

import { AgentAvatar } from "@/components/agent-avatar";
import { AgentRoom } from "@/components/agent-room";
import { agentById, agents, canonicalAgentIds, validateAgentRegistry } from "@/lib/agents";

const paths = {
  "creative-director": "/agents/creative-director.png",
  "concept-generator": "/agents/concept-generator.png",
  "prompt-agent": "/agents/prompt-agent.png",
  "social-intelligence": "/agents/social-intelligence.png",
  "art-review": "/agents/art-review.png",
  "brand-integration": "/agents/brand-integration.png",
  "motion-director": "/agents/motion-director.png",
};

describe("canonical agent portraits", () => {
  it("maps all seven agents to the supplied production assets", () => {
    expect(agents).toHaveLength(7);
    expect(validateAgentRegistry()).toEqual([]);
    for (const id of canonicalAgentIds) {
      expect(agentById(id)?.avatarPath).toBe(paths[id]);
      expect(agentById(id)?.route).toBe(`/agents/${id}`);
    }
  });

  it("keeps legacy identities as aliases without duplicate agents", () => {
    expect(agentById("content-agent")?.id).toBe("concept-generator");
    expect(agentById("prompt-engineer")?.id).toBe("prompt-agent");
    expect(agentById("art-reviewer")?.id).toBe("art-review");
    expect(agentById("brand-partnerships")?.id).toBe("brand-integration");
    expect(agentById("social-learning")?.id).toBe("social-intelligence");
  });

  it("renders the portrait and degrades to a neutral initials fallback", () => {
    render(<AgentAvatar agentId="motion-director" size="lg"/>);
    const image = screen.getByAltText("Motion Director DINKLY agent");
    expect(image).toHaveAttribute("src", expect.stringContaining("motion-director.png"));
    fireEvent.error(image);
    expect(screen.getByLabelText("Motion Director DINKLY agent portrait unavailable")).toHaveTextContent("MD");
  });

  it("uses the same portrait in a generic agent room header", () => {
    const agent = agentById("brand-integration")!;
    render(<AgentRoom agent={agent}/>);
    expect(screen.getByAltText("Brand Integration DINKLY agent")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Brand Integration" })).toBeInTheDocument();
  });
});
