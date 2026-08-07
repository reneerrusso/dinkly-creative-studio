import { describe, expect, it } from "vitest";

import { isNewStory } from "@/lib/story-seed";

describe("Story Library New tag", () => {
  const now = Date.parse("2026-08-07T18:00:00Z");

  it("marks an approved concept as new for its first 24 hours", () => {
    expect(isNewStory({ added_to_library_at: "2026-08-06T18:00:01Z" }, now)).toBe(true);
  });

  it("removes the new state at 24 hours", () => {
    expect(isNewStory({ added_to_library_at: "2026-08-06T18:00:00Z" }, now)).toBe(false);
  });

  it("does not mark seeded stories without a saved timestamp", () => {
    expect(isNewStory({}, now)).toBe(false);
  });
});
