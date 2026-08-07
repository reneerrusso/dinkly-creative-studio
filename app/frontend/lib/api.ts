import type {
  Concept,
  DashboardData,
  Learning,
  PatternData,
  SocialPost,
  SpriteAnimation,
  SpriteCharacter,
  SpriteComposition,
  SpriteExport,
  AgentRun,
  CompetitorDirection,
  CompetitorLearning,
  CompetitorPost,
  MonitoredHandle,
  ProviderPreflight,
  SocialProviderStatus,
} from "@/lib/types";

const LOCAL_API_URL = "http://127.0.0.1:8000";

export function resolveApiBaseUrl(value?: string): string {
  const candidate = value?.trim() || LOCAL_API_URL;
  let resolved: URL;
  try {
    resolved = new URL(candidate);
  } catch {
    throw new Error("Invalid NEXT_PUBLIC_API_URL. Use an absolute http:// or https:// backend URL.");
  }
  if (!['http:', 'https:'].includes(resolved.protocol) || resolved.username || resolved.password || resolved.search || resolved.hash) {
    throw new Error("Invalid NEXT_PUBLIC_API_URL. Use an absolute http:// or https:// backend URL without credentials, query parameters, or fragments.");
  }
  return resolved.href.replace(/\/$/, "");
}

export const API_URL = resolveApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export interface ApiRequestInit extends RequestInit {
  timeoutMs?: number;
}

export async function api<T>(path: string, init?: ApiRequestInit): Promise<T> {
  if (!path.startsWith("/")) throw new ApiError(`API request path must start with /: ${path}`, 0);
  const { timeoutMs = 20_000, signal: callerSignal, ...requestInit } = init ?? {};
  const controller = new AbortController();
  const forwardAbort = () => controller.abort();
  if (callerSignal?.aborted) controller.abort();
  else callerSignal?.addEventListener("abort", forwardAbort, { once: true });
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const requestUrl = new URL(path, `${API_URL}/`).toString();
  if (process.env.NODE_ENV !== "production" && path.startsWith("/api/slack")) {
    const resolved = new URL(API_URL);
    console.info("[DINKLY API]", { requestPath: path, resolvedApiBaseUrl: API_URL, backendPort: resolved.port || (resolved.protocol === "https:" ? "443" : "80") });
  }
  try {
    const response = await fetch(requestUrl, {
      ...requestInit,
      headers: {
        ...(requestInit.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...requestInit.headers,
      },
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new ApiError(payload?.detail ?? `Request failed with ${response.status}`, response.status);
    }
    return response.json() as Promise<T>;
  } catch (error) {
    if (controller.signal.aborted && !callerSignal?.aborted) {
      throw new ApiError("The Generation Engine API did not respond. Keep pnpm dev running, then try again.", 0);
    }
    if (error instanceof TypeError) {
      throw new ApiError(`Backend unreachable at ${API_URL}. Confirm the FastAPI service and CORS configuration.`, 0);
    }
    throw error;
  } finally {
    clearTimeout(timeout);
    callerSignal?.removeEventListener("abort", forwardAbort);
  }
}

export async function downloadApiFile(path: string): Promise<string> {
  if (!path.startsWith("/")) throw new ApiError(`API request path must start with /: ${path}`, 0);
  let response: Response;
  try {
    response = await fetch(new URL(path, `${API_URL}/`).toString(), { cache: "no-store" });
  } catch {
    throw new ApiError(`Backend unreachable at ${API_URL}.`, 0);
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(payload?.detail ?? `Download failed with ${response.status}`, response.status);
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  const filename = encoded ? decodeURIComponent(encoded) : plain || "dinkly-download";
  const objectUrl = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
  return filename;
}

export const getDashboard = () => api<DashboardData>("/api/dashboard");
export const getConcepts = () => api<Concept[]>("/api/concepts");
export const getSocialPosts = () => api<SocialPost[]>("/api/social-posts");
export const getLearnings = () => api<Learning[]>("/api/social-learnings");
export const getPatterns = () => api<PatternData>("/api/social-patterns");
export const getSpriteCharacters = () => api<SpriteCharacter[]>("/api/sprite-characters");
export const getSpriteAnimations = (query = "") => api<SpriteAnimation[]>(`/api/sprite-animations${query}`);
export const getSpriteAnimation = (id: string) => api<SpriteAnimation>(`/api/sprite-animations/${id}`);
export const getSpriteCompositions = () => api<SpriteComposition[]>("/api/sprite-compositions");
export const getSpriteExports = () => api<SpriteExport[]>("/api/sprite-exports");
export const getSocialDataProviders = () => api<SocialProviderStatus[]>("/api/social-data-providers");
export const getMonitoredHandles = () => api<MonitoredHandle[]>("/api/monitored-handles");
export const getCompetitorPosts = () => api<CompetitorPost[]>("/api/competitor-posts");
export const getCompetitorLearnings = () => api<CompetitorLearning[]>("/api/competitor-learnings");
export const getCompetitorDirections = () => api<CompetitorDirection[]>("/api/competitor-concepts");
export const getAgentRuns = () => api<AgentRun[]>("/api/agent-runs");
export const getProviderPreflight = (body: Record<string, unknown> = {}) => api<ProviderPreflight>("/api/monitored-handles/preflight", { method: "POST", body: JSON.stringify(body) });

export function spriteAssetUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http") || path.startsWith("/sprite-assets/")) return `${API_URL}${path}`;
  const marker = "app-data/sprites/";
  return path.includes(marker) ? `${API_URL}/sprite-assets/${path.split(marker)[1]}` : path;
}
