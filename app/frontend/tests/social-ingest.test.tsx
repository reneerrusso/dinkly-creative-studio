import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import IngestPage from "@/app/social-learning/ingest/page";

describe("social post ingestion", () => {
  it("shows unknown metrics as optional rather than zero", async () => {
    const user = userEvent.setup();
    render(<IngestPage/>);
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await user.type(screen.getByPlaceholderText("Sunday Morning carousel"), "Sunday Morning carousel");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(screen.getByTestId("missing-metrics")).toHaveTextContent("Leave blank if unknown");
    expect(screen.getByText(/0 of 5 core metrics supplied/i)).toBeInTheDocument();
  });
});
