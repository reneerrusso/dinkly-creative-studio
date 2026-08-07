import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ArtReviewPage from "@/app/art-review/page";

describe("art review failure selection", () => {
  it("lets the reviewer select precise failures", async () => {
    const user = userEvent.setup();
    render(<ArtReviewPage/>);
    const chip = screen.getByRole("button", { name: "Wrong eyes" });
    await user.click(chip);
    expect(chip).toHaveClass("bg-ink");
  });
});
