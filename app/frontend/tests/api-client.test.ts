import { resolveApiBaseUrl } from "@/lib/api";

describe("canonical API URL configuration", () => {
  it("uses the local FastAPI URL when the environment value is missing or blank", () => {
    expect(resolveApiBaseUrl()).toBe("http://127.0.0.1:8000");
    expect(resolveApiBaseUrl("   ")).toBe("http://127.0.0.1:8000");
  });

  it("normalizes a valid localhost URL", () => {
    expect(resolveApiBaseUrl("  http://localhost:8000/  ")).toBe("http://localhost:8000");
  });

  it("rejects malformed values before fetch can throw a generic URL error", () => {
    expect(() => resolveApiBaseUrl("localhost:8000")).toThrow("Invalid NEXT_PUBLIC_API_URL");
    expect(() => resolveApiBaseUrl("undefined/api")).toThrow("Invalid NEXT_PUBLIC_API_URL");
  });
});
