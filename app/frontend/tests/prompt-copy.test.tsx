import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PromptPreview } from "@/components/prompt-preview";

describe("prompt preview", () => {
  it("copies the full production prompt", async () => {
    render(<PromptPreview prompt="REFERENCE PRIORITY\nUse the locked DINKLY model sheet."/>);
    fireEvent.click(screen.getByRole("button", { name: /copy prompt/i }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith("REFERENCE PRIORITY\nUse the locked DINKLY model sheet."));
  });
});
