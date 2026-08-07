import { describe, expect, it } from "vitest";

import { developStorySeed } from "@/lib/story-seed";

describe("Story Library concept handoff", () => {
  it("develops the selected seed instead of the Coffee fallback", () => {
    const developed = developStorySeed({
      id: "story-laundry",
      title: "Laundry",
      title_direction: "LAUNDRY / LAUNDRY WITH YOU",
      concept: "Chores become companionship",
      visual_distinction: "Floor-level baskets, folded stack, wide view",
      category: "Home",
      format: "x-with-you",
      approved: true,
    });

    expect(developed.form.leftTitle).toBe("LAUNDRY");
    expect(developed.form.rightTitle).toBe("LAUNDRY WITH YOU");
    expect(developed.form.leftCharacter).toBe("boy");
    expect(developed.form.leftEmotion).toContain("never happy");
    expect(developed.form.leftCharacterAction).not.toContain("coffee");
    expect(developed.form.cameraAngle).toBe("wide straight-on");
    expect(developed.props).toContain("floor-level laundry baskets");
  });

  it("preserves a version-2 Girl DINKLY left-panel selection", () => {
    const developed = developStorySeed({
      id: "story-party-girl",
      title: "Party",
      title_left: "PARTY",
      title_right: "PARTY WITH YOU",
      concept: "A party feels warmer together",
      category: "Weekends",
      format: "x-with-you",
      approved: true,
      left_character: "girl",
      left_character_action: "stands alone with one red cup",
      left_setting: "a small party room",
      left_props: ["red cup", "deflated balloons"],
      left_emotion: "Nervous and unsure.",
      right_character_actions: "laugh and dance together",
      right_setting: "the same small party room",
      right_props: ["two cups", "floating balloons"],
      right_emotion: "Warm and lively.",
      shared_environment: "Same party room.",
      environmental_contrast: "Stillness becomes movement.",
    });
    expect(developed.form.leftCharacter).toBe("girl");
    expect(developed.form.leftProps).toEqual(["red cup", "deflated balloons"]);
    expect(developed.form.rightCharacterActions).toBe("laugh and dance together");
  });
});
