import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AppSidebar } from "@/components/app-sidebar";
import { agents } from "@/lib/agents";

describe("navigation", () => {
  it("leads with the single DINKLY Agent employee workflow", () => {
    render(<AppSidebar />);
    for (const label of ["DINKLY Agent", "Approvals", "Comics", "Activity", "Settings"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    for (const label of agents.map(agent => agent.displayName)) expect(screen.queryByText(label)).not.toBeInTheDocument();
  });

  it("collapses the Brain by default and reveals its documentation on request", async () => {
    const user = userEvent.setup();
    render(<AppSidebar />);
    expect(screen.queryByText("Story Library")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /brain/i }));
    for (const label of ["Story Library", "Used Storylines", "Examples", "Knowledge Base", "Failure Library"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    for (const label of ["Character Bible", "Style Guide", "Prompt Templates"]) expect(screen.queryByText(label)).not.toBeInTheDocument();
  });

  it("gives every agent a persistent illustrated identity and a working room route", () => {
    for (const agent of agents) {
      expect(agent.avatarPath).toMatch(/^\/agents\/.+\.png$/);
      expect(agent.personality.length).toBeGreaterThan(20);
      expect(agent.objective.length).toBeGreaterThan(30);
      expect(agent.actions.length).toBeGreaterThanOrEqual(3);
      expect(agent.route).toBe(`/agents/${agent.id}`);
    }
  });

  it("keeps the focused workflow as compact desktop navigation", async () => {
    const user = userEvent.setup();
    render(<AppSidebar />);
    await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(screen.getByTitle("DINKLY Agent")).toBeInTheDocument();
    expect(screen.getByTitle("Approvals")).toBeInTheDocument();
    expect(screen.getByTitle("Comics")).toBeInTheDocument();
    expect(screen.getByTitle("Activity")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeInTheDocument();
  });
});
