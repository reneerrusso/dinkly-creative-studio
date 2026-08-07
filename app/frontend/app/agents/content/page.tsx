import { permanentRedirect } from "next/navigation";

export default function LegacyContentAgentRedirect({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(searchParams)) {
    if (Array.isArray(value)) value.forEach(item => query.append(key, item));
    else if (value !== undefined) query.set(key, value);
  }
  permanentRedirect(`/agents/concept-generator${query.size ? `?${query}` : ""}`);
}
