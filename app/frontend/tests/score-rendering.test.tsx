import { render, screen } from "@testing-library/react";
import { ScoreBadge } from "@/components/score-badge";

describe("directional score", () => {
  it("renders a score without claiming predicted performance", () => {
    render(<ScoreBadge score={8.4}/>);
    expect(screen.getByTestId("score-badge")).toHaveTextContent("8.4/10");
  });
});
