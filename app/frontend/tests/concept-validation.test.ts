import { conceptSchema } from "@/lib/schemas";

describe("concept validation", () => {
  it("rejects an incomplete creative brief", () => {
    const result = conceptSchema.safeParse({ format: "x-with-you", leftTitle: "COFFEE" });
    expect(result.success).toBe(false);
  });

  it("accepts an explicit two-panel emotional contrast", () => {
    const result = conceptSchema.safeParse({
      format: "x-with-you", leftTitle: "COFFEE", rightTitle: "COFFEE WITH YOU",
      leftCharacter: "girl", category: "Food and drinks", theme: "companionship",
      emotionalInsight: "A small routine feels warmer when it is shared.",
      leftCharacterAction: "sits alone with one mug", leftSetting: "a small café",
      leftProps: ["mug", "small table"], leftEmotion: "Neutral and bored.",
      rightCharacterActions: "share coffee and look at each other", rightSetting: "the same small café",
      rightProps: ["two mugs", "small table"], rightEmotion: "Warm and connected.",
      sharedEnvironment: "Same café and table.", environmentalContrast: "One mug becomes two and stillness becomes connection.",
      background: "warm cream", accentColor: "muted mustard", cameraAngle: "medium straight-on",
      brandFriendly: true, productCategory: "coffee", naturalProductPlacement: "One natural coffee bag.",
      executionRisks: ["Keep mugs correctly scaled"], notes: "",
    });
    expect(result.success).toBe(true);
  });

  it("rejects an invalid left-panel character", () => {
    const result = conceptSchema.safeParse({ ...completeConcept(), leftCharacter: "either" });
    expect(result.success).toBe(false);
  });
});

function completeConcept() {
  return {
    format: "x-with-you", leftTitle: "RAIN", rightTitle: "RAIN WITH YOU", leftCharacter: "boy",
    category: "Seasons", theme: "care", emotionalInsight: "Shared shelter makes rain feel warmer.",
    leftCharacterAction: "waits alone", leftSetting: "a quiet park path", leftProps: ["umbrella", "leaf"], leftEmotion: "Neutral.",
    rightCharacterActions: "stand close together", rightSetting: "the same quiet park path", rightProps: ["umbrella", "two cups"], rightEmotion: "Warm.",
    sharedEnvironment: "Same path.", environmentalContrast: "The same rain feels warmer together.", background: "dusty blue",
    accentColor: "muted coral", cameraAngle: "medium straight-on", brandFriendly: false, productCategory: "",
    naturalProductPlacement: "", executionRisks: [], notes: "",
  };
}
