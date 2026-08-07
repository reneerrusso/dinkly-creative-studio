import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SlackSettings } from "@/components/slack-settings";

const status = {
  connected: true,
  connection_status: "Connected",
  mode: "socket_mode",
  workspace_id: "T1",
  workspace_name: "DINKLY",
  bot_user_id: "B1",
  bot_name: "DINKLY Bot",
  default_channel: null,
  allowed_users: ["U1"],
  notifications: {},
  configured: true,
  socket_mode_configured: true,
  socket_mode_active: true,
  socket_mode_status: "Connected",
  tls_status: "Connected",
  slack_api_status: "Connected",
};

describe("Slack Settings connection test", () => {
  it("tests auth and Socket Mode without requiring a default channel", async () => {
    const user = userEvent.setup();
    vi.mocked(globalThis.fetch).mockImplementation(async (input, init) => {
      if (String(input).endsWith("/api/slack/status")) return { ok: true, json: async () => status } as Response;
      if (String(input).endsWith("/api/slack/test") && init?.method === "POST") return { ok: true, json: async () => status } as Response;
      return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) } as Response;
    });

    render(<SlackSettings/>);
    const testButton = await screen.findByRole("button", { name: "Test Slack" });
    expect(testButton).toBeEnabled();
    await user.click(testButton);

    await waitFor(() => expect(vi.mocked(globalThis.fetch).mock.calls.some(([input]) => String(input).endsWith("/api/slack/test"))).toBe(true));
    expect(screen.getByText("DINKLY")).toBeInTheDocument();
    expect(screen.getByText("DINKLY Bot")).toBeInTheDocument();
    expect(screen.getAllByText("Connected").length).toBeGreaterThanOrEqual(4);
  });

  it("separates TLS diagnostics and offers a retry without revealing credentials", async () => {
    const user = userEvent.setup();
    const failed = {
      ...status,
      connected: false,
      connection_status: "Could not verify Slack’s HTTPS certificate from the local Python environment",
      tls_status: "Could not verify Slack’s HTTPS certificate from the local Python environment",
      slack_api_status: "Not tested",
      socket_mode_status: "Not tested",
    };
    vi.mocked(globalThis.fetch).mockImplementation(async input => {
      const url = String(input);
      if (url.endsWith("/api/slack/status")) return { ok: true, json: async () => failed } as Response;
      if (url.endsWith("/api/slack/diagnostics")) return { ok: true, json: async () => ({ python_version: "3.11.1", openssl_version: "OpenSSL 1.1.1q", certifi_version: "2026.7.22", certifi_path: "/safe/certifi/cacert.pem", tls_verification_status: "Ready — certifi CA bundle", slack_api_reachable: false, socket_mode_status: "Not tested" }) } as Response;
      return { ok: false, status: 503, json: async () => ({ detail: "Backend unavailable" }) } as Response;
    });

    render(<SlackSettings/>);
    expect(await screen.findByRole("button", { name: "Retry" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "View diagnostics" }));
    expect(await screen.findByText("Ready — certifi CA bundle")).toBeInTheDocument();
    expect(screen.queryByText(/xoxb-/)).not.toBeInTheDocument();
  });
});
