import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import SocialIntelligencePage from "@/app/agents/social-intelligence/page";
import { SocialProviderSettings } from "@/components/social-provider-settings";

const budgetSettings = {
  enable_paid_provider_calls: false,
  maximum_estimated_cost_per_run: 1,
  daily_provider_budget: 2,
  monthly_provider_budget: 5,
  maximum_handles_per_refresh: 5,
  maximum_posts_per_handle: 20,
  maximum_provider_requests_per_run: 10,
  maximum_retries: 2,
  require_confirmation_above_estimated_cost: 0.5,
  automatically_pause_at_80_percent: true,
  hard_stop_at_100_percent: true,
  allow_paid_overage: false,
  schedule_enabled: false,
  schedule_frequency: "Weekly",
  connection_timeout_seconds: 10,
  read_timeout_seconds: 30,
  actor_run_timeout_seconds: 180,
  download_timeout_seconds: 20,
};
const usage = { daily_used: 0, daily_remaining: 2, monthly_used: 0, monthly_remaining: 5, monthly_budget: 5, percent_used: 0, percent_remaining: 100, approaching_limit: false, hard_limit_reached: false };
const noProvider = { name: "Apify", state: "Not configured", configured: false, paused: false, budget: usage, message: "Add an Apify API key or use manual import." };
const configuredProvider = { ...noProvider, state: "Configured", configured: true, masked_token: "••••••••••••abcd", instagram_actor_id: "", tiktok_actor_id: "", platforms: { instagram: { platform: "instagram", enabled: true, source: "recommended", actor_override: "", last_verified_at: "2026-08-06T00:00:00Z", verification_status: "runtime_verified", actor_name: "Instagram Scraper", actor_owner: "Apify", pricing_summary: "Pay per result" }, tiktok: { platform: "tiktok", enabled: true, source: "recommended", actor_override: "", last_verified_at: "2026-08-06T00:00:00Z", verification_status: "runtime_verified", actor_name: "TikTok Profile Scraper", actor_owner: "Clockworks", pricing_summary: "Pay per result" } }, message: "Connection healthy" };
const handle = { id: "handle-1", platform: "instagram", username: "example", canonical_url: "https://instagram.com/example/", display_name: null, category: "Inspiration", enabled: true, provider: "apify", posts_per_refresh: 10, refresh_frequency: "Off", last_checked_at: null, last_success_at: null, last_error: null, follower_count: 1000 };

function response(payload: unknown, ok = true, status = 200) { return { ok, status, json: async () => payload } as Response; }

function mockBackend(options: { provider?: typeof noProvider; handles?: unknown[]; posts?: unknown[]; learnings?: unknown[]; directions?: unknown[]; runs?: unknown[]; usage?: typeof usage; paid?: boolean } = {}) {
  const provider = options.provider ?? noProvider;
  const budgetUsage = options.usage ?? usage;
  vi.mocked(globalThis.fetch).mockImplementation(async input => {
    const url = String(input);
    if (url.endsWith("/api/social-data-providers")) return response([provider, { name: "manual-import", state: "Available", configured: true }]);
    if (url.endsWith("/api/provider-budget")) return response({ settings: { ...budgetSettings, enable_paid_provider_calls: options.paid ?? false }, usage: budgetUsage, provider: { status: provider.state, paused: provider.paused, circuit_state: "Closed", message: provider.message } });
    if (url.endsWith("/api/monitored-handles")) return response(options.handles ?? []);
    if (url.endsWith("/api/competitor-posts")) return response(options.posts ?? []);
    if (url.endsWith("/api/competitor-posts/import")) return response({ posts_created: 1, posts_skipped: 0, snapshots_created: 1, errors: [] });
    if (url.endsWith("/api/competitor-learnings")) return response(options.learnings ?? []);
    if (url.endsWith("/api/competitor-concepts")) return response(options.directions ?? []);
    if (url.endsWith("/api/agent-runs")) return response(options.runs ?? []);
    if (url.endsWith("/api/social-data-providers/test")) return response({ connected: true, message: "Connection test complete.", token: { status: "Connected" }, platforms: { instagram: { status: "Ready", ready: true }, tiktok: { status: "Ready", ready: true } } });
    if (url.includes("/api/social-data-providers/apify/configure")) return response({ configuration: { configured: false } });
    if (url.endsWith("/api/monitored-handles/bulk/preview")) return response({ count: 1, handles: [{ platform: "instagram", username: "newaccount", canonical_url: "https://instagram.com/newaccount/", duplicate: false, category: "Other" }] });
    if (url.endsWith("/api/monitored-handles/bulk")) return response({ created: 1, handles: [] });
    if (url.endsWith("/api/monitored-handles/preflight")) return response({ handles: 1, platforms: ["Instagram"], maximum_posts: 10, estimated_cost_low: 0.05, estimated_cost_high: 0.18, estimated_cost_label: "Estimated provider cost", daily_budget_remaining: 2, monthly_budget_remaining: 5, requires_confirmation: true, can_run: true, warnings: ["The selected Actor has never been run before."], hard_stops: [], provider_health: "Configured" });
    if (url.endsWith("/api/monitored-handles/refresh")) return response({ run: { id: "run-1", kind: "social-intelligence-refresh", status: "Running", summary: {}, warnings: [], error: null, created_at: "2026-08-06T12:00:00Z", completed_at: null } });
    if (url.includes("/approve")) return response({ status: "Approved" });
    if (url.includes("/open-in-prompt-builder")) return response({ href: "/prompt-builder?concept=concept-1" });
    return response({});
  });
}

describe("Social Intelligence Agent", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("keeps the first run calm and usable with no API key or fabricated records", async () => {
    mockBackend();
    render(<SocialIntelligencePage/>);
    expect(await screen.findByText("Connect a provider or import data manually.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Apify API key" })).toBeInTheDocument();
    expect(screen.getByText("0 posts")).toBeInTheDocument();
    expect(screen.getByText("No monitored handles")).toBeInTheDocument();
  });

  it("shows only the saved-token mask, tests the connection, and requires key-removal confirmation", async () => {
    const user = userEvent.setup();
    mockBackend({ provider: configuredProvider });
    render(<SocialProviderSettings/>);
    expect(await screen.findByText("••••••••••••abcd")).toBeInTheDocument();
    expect(screen.queryByDisplayValue(/abcd/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Test connection" }));
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/social-data-providers/test"), expect.objectContaining({ method: "POST" })));
    await user.click(screen.getByRole("button", { name: "Remove key" }));
    expect(screen.getByRole("button", { name: "Confirm remove key" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm remove key" }));
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/social-data-providers/apify/configure"), expect.objectContaining({ method: "DELETE" })));
  });

  it("sends a new key only through the active setup form and clears it after save", async () => {
    const user = userEvent.setup();
    mockBackend();
    render(<SocialProviderSettings/>);
    const token = await screen.findByLabelText("Apify API token");
    await user.type(token, "fixture_token_abcd");
    expect(screen.queryByLabelText("Instagram Actor Override")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save securely" }));
    await waitFor(() => expect(token).toHaveValue(""));
    const configureCall = vi.mocked(globalThis.fetch).mock.calls.find(([url]) => String(url).endsWith("/api/social-data-providers/apify/configure"));
    expect(configureCall?.[1]).toEqual(expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(String(configureCall?.[1]?.body))).toEqual(expect.objectContaining({ token: "fixture_token_abcd", instagram_actor_id: "", tiktok_actor_id: "", instagram_enabled: true, tiktok_enabled: true }));
  });

  it("keeps Actor overrides in Advanced Settings and uses blank recommended defaults", async () => {
    const user = userEvent.setup();
    mockBackend({ provider: configuredProvider });
    render(<SocialProviderSettings/>);
    expect(await screen.findAllByText("Using recommended Actor")).toHaveLength(2);
    expect(screen.queryByLabelText("Instagram Actor Override")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Advanced Settings/ }));
    expect(screen.getByLabelText("Instagram Actor Override")).toHaveValue("");
    expect(screen.getByLabelText("TikTok Actor Override")).toHaveValue("");
  });

  it("renders budget and provider hard-stop warnings without hiding manual controls", async () => {
    const stoppedUsage = { ...usage, monthly_used: 5, monthly_remaining: 0, percent_used: 100, percent_remaining: 0, approaching_limit: true, hard_limit_reached: true };
    mockBackend({ provider: { ...configuredProvider, state: "Budget paused", paused: true, message: "Apify declined the request because the account has insufficient usage credit." }, usage: stoppedUsage });
    render(<SocialProviderSettings/>);
    expect(await screen.findByText("Approaching your monthly provider budget.")).toBeInTheDocument();
    expect(screen.getByText("Provider calls paused to prevent additional charges.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resume provider" })).toBeInTheDocument();
    expect(screen.getByText(/insufficient usage credit/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Enable paid provider calls")).not.toBeChecked();
  });

  it("previews a bounded provider cost before creating a live run", async () => {
    const user = userEvent.setup();
    let source: FakeEventSource | undefined;
    class FakeEventSource {
      onerror: (() => void) | null = null;
      listeners = new Map<string, (event: MessageEvent) => void>();
      constructor(public url: string) { source = this; }
      addEventListener(kind: string, listener: EventListener) { this.listeners.set(kind, listener as (event: MessageEvent) => void); }
      emit(kind: string, payload: unknown) { this.listeners.get(kind)?.({ data: JSON.stringify(payload) } as MessageEvent); }
      close() {}
    }
    vi.stubGlobal("EventSource", FakeEventSource);
    mockBackend({ provider: configuredProvider, handles: [handle], paid: true });
    render(<SocialIntelligencePage/>);
    await user.click(await screen.findByRole("button", { name: "Refresh handles" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("$0.05–$0.18")).toBeInTheDocument();
    expect(within(dialog).getByText("Estimated provider cost")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Confirm and run" }));
    expect(await screen.findByText("Waiting for the first persisted backend event…")).toBeInTheDocument();
    source?.emit("scope", { id: "event-1", run_id: "run-1", timestamp: "2026-08-06T12:00:01Z", level: "info", kind: "scope", message: "Loaded 1 monitored handle.", data: {} });
    expect(await screen.findByText("Loaded 1 monitored handle.")).toBeInTheDocument();
  });

  it("normalizes a bulk handle preview before saving monitoring", async () => {
    const user = userEvent.setup();
    mockBackend();
    render(<SocialIntelligencePage/>);
    await user.click((await screen.findAllByRole("button", { name: "Add handles" }))[0]);
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByPlaceholderText(/instagram,@example/), "Instagram,@NewAccount");
    await user.click(within(dialog).getByRole("button", { name: "Preview handles" }));
    expect(await within(dialog).findByText("@newaccount")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Save new handles" }));
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/monitored-handles/bulk"), expect.objectContaining({ method: "POST" })));
  });

  it("keeps manual JSON import available without a configured provider", async () => {
    const user = userEvent.setup();
    mockBackend();
    render(<SocialIntelligencePage/>);
    const input = await screen.findByLabelText("Import data");
    await user.upload(input, new File([JSON.stringify([{ platform: "instagram", username: "manual", id: "p1" }])], "posts.json", { type: "application/json" }));
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/competitor-posts/import"), expect.objectContaining({ method: "POST", body: expect.any(FormData) })));
  });

  it("shows partial runs, explores real posts, and approves an evidence learning", async () => {
    const user = userEvent.setup();
    const post = { id: "post-1", handle_id: "handle-1", platform: "instagram", platform_post_id: "p1", post_url: "https://example.com/p1", caption: "A quiet coffee ritual", posted_at: "2026-08-01T12:00:00Z", media_type: "image", remote_thumbnail_url: null, view_count: 0, like_count: 10, comment_count: null, share_count: null, creative_attributes: { activity: "coffee", theme: "comfort", format: "split", classification_source: "manual correction" }, handle: { username: "example" }, performance: { primary_metric: "view_count", account_median: 0, account_average: 0, percentile_rank: 100, multiplier: null, sample_size: 1 }, metric_completeness: { known: 2, total: 4, percent: 0.5 }, snapshot_count: 1, velocity_message: "More snapshots are needed to calculate velocity." };
    const learning = { id: "learning-1", classification: "Observed pattern", pattern: "Quiet rituals include a standout.", measured_fact: "One collected record is above its account median.", hypothesis: "Familiarity may help recognition.", recommendation: "Test an original DINKLY ritual.", data_limitation: "The sample is one post.", confidence: "Low", sample_size: 1, evidence_post_ids: ["post-1"], status: "Pending" };
    const run = { id: "run-partial", kind: "social-intelligence-refresh", status: "Completed with warnings", summary: { handles_processed: 1, posts_fetched: 1 }, warnings: ["TikTok unavailable"], error: null, created_at: "2026-08-06T12:00:00Z", completed_at: "2026-08-06T12:01:00Z" };
    mockBackend({ provider: configuredProvider, handles: [handle], posts: [post], learnings: [learning], runs: [run], paid: true });
    render(<SocialIntelligencePage/>);
    await user.click(await screen.findByRole("tab", { name: "Posts" }));
    expect(screen.getAllByText("0").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.getByText("50% metrics known")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Learnings" }));
    await user.click(screen.getByRole("button", { name: "Approve learning" }));
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/approve"), expect.objectContaining({ method: "POST" })));
    await user.click(screen.getByRole("tab", { name: "Runs" }));
    expect(screen.getByText("Completed with warnings")).toBeInTheDocument();
  });

  it("exposes safe schedule and timeout controls in provider settings", async () => {
    mockBackend();
    render(<SocialProviderSettings/>);
    await screen.findByText("Provider budget guardrails");
    const details = screen.getByText("Scheduling and advanced timeouts");
    details.click();
    expect(screen.getByLabelText("Enable local schedule")).not.toBeChecked();
    expect(screen.getByText("Read timeout")).toBeInTheDocument();
    expect(screen.getByText("Download timeout")).toBeInTheDocument();
  });

  it("hands an original direction to the existing Prompt Builder route", async () => {
    const user = userEvent.setup();
    const direction = { id: "direction-1", signal: "A supported ritual signal", source_pattern: "A high-level ritual", reusable_principle: "Use one familiar shared routine", must_not_copy: "Do not copy source layout or words", dinkly_emotional_angle: "Ordinary life is warmer together", title_pair: { left: "RAIN", right: "RAIN WITH YOU" }, left_scene: "Dinko waits alone under one umbrella.", right_scene: "Dinka and Dinko share the umbrella.", shared_setting: "Simple rainy sidewalk", purposeful_props: ["umbrella"], pastel_background: "powder blue", accent_color: "muted coral", execution_risks: ["No long legs"], why_original: "New DINKLY scene", why_someone_may_share: "A recognizable routine", confidence: "Low", status: "Draft", concept_id: null };
    mockBackend({ provider: configuredProvider, directions: [direction], paid: true });
    render(<SocialIntelligencePage/>);
    await user.click(await screen.findByRole("tab", { name: "Concept Directions" }));
    await user.click(screen.getByRole("button", { name: /Open in Prompt Builder/ }));
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/open-in-prompt-builder"), expect.objectContaining({ method: "POST" })));
  });
});
