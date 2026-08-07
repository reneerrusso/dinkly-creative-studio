import type { ConceptFormValues } from "@/lib/schemas";

export interface StorySeed {
  id: string;
  title_left?: string;
  title_right?: string;
  title: string;
  title_direction?: string;
  concept: string;
  visual_distinction?: string;
  category: string;
  format: string;
  left_character?: "boy" | "girl";
  left_character_action?: string;
  left_setting?: string;
  left_props?: string[];
  left_emotion?: string;
  right_characters?: "boy_and_girl";
  right_character_actions?: string;
  right_setting?: string;
  right_props?: string[];
  right_emotion?: string;
  shared_environment?: string;
  environmental_contrast?: string;
  background_color?: string;
  accent_color?: string;
  camera_angle?: string;
  prop_count?: number;
  brand_friendly?: boolean;
  brand_categories?: string[];
  execution_risks?: string[];
  notes?: string | null;
  status?: string;
  migration_version?: 2;
  scene_richness?: "Sparse" | "Balanced" | "Detailed";
  scene_warnings?: string[];
  approved: boolean;
  example_available?: boolean;
  source_concept_id?: string;
  created_at?: string;
  added_to_library_at?: string;
}

export function isNewStory(story: Pick<StorySeed, "added_to_library_at" | "created_at">, now = Date.now()): boolean {
  const timestamp = story.added_to_library_at ?? story.created_at;
  if (!timestamp) return false;
  const addedAt = Date.parse(timestamp);
  if (!Number.isFinite(addedAt)) return false;
  const age = now - addedAt;
  return age >= 0 && age < 24 * 60 * 60 * 1000;
}

export interface DevelopedStorySeed {
  form: ConceptFormValues;
  props: string[];
  executionRisks: string[];
  brandPlacementOpportunities: string[];
  novelAngle: string;
  whySomeoneWouldShare: string;
}

function titlePair(story: StorySeed) {
  const pieces = (story.title_direction ?? "").split(/\s*\/\s*/).filter(Boolean);
  const left = story.title_left ?? pieces[0] ?? story.title.toUpperCase();
  const right = story.title_right ?? pieces[1] ?? `${left} WITH YOU`;
  return { left, right };
}

function legacyProps(story: StorySeed): string[] {
  const value = `${story.title} ${story.visual_distinction ?? ""}`.toLowerCase();
  const candidates: Array<[RegExp, string]> = [
    [/laundry|basket/, "floor-level laundry baskets"], [/coffee|mug/, "mug"], [/table/, "small rounded table"],
    [/chair|seat/, "rounded chair"], [/blanket/, "shared blanket"], [/umbrella/, "umbrella"],
    [/game|board/, "simple board game"], [/market|produce/, "produce stand"], [/book/, "book"],
    [/television|movies|tv/, "small television"], [/cart|shopping/, "shopping cart"], [/toothbrush/, "toothbrush"],
  ];
  return candidates.filter(([pattern]) => pattern.test(value)).map(([, prop]) => prop).slice(0, 3);
}

function legacyCamera(story: StorySeed) {
  const value = story.visual_distinction?.toLowerCase() ?? "";
  if (value.includes("overhead")) return "overhead medium-wide";
  if (value.includes("profile")) return "medium profile view";
  if (value.includes("wide")) return "wide straight-on";
  if (value.includes("close-up")) return "close-up straight-on";
  return "medium straight-on";
}

export function developStorySeed(story: StorySeed): DevelopedStorySeed {
  const titles = titlePair(story);
  const leftCharacter = story.left_character ?? "boy";
  const characterName = leftCharacter === "girl" ? "Girl DINKLY" : "Boy DINKLY";
  const leftProps = story.left_props?.length ? story.left_props : legacyProps(story);
  const rightProps = story.right_props?.length ? story.right_props : legacyProps(story);
  const leftSetting = story.left_setting || story.visual_distinction || "a minimal environment for the activity";
  const rightSetting = story.right_setting || leftSetting;
  const leftAction = story.left_character_action || `${characterName} experiences ${story.title.toLowerCase()} alone`;
  const rightActions = story.right_character_actions || `Boy DINKLY and Girl DINKLY share the same ${story.title.toLowerCase()} activity`;
  const leftEmotion = story.left_emotion || "Neutral, bored, or gently sad—never happy.";
  const rightEmotion = story.right_emotion || "Warmly connected because the activity is shared.";
  const sharedEnvironment = story.shared_environment || `The same ${leftSetting.toLowerCase()} continues across both panels.`;
  const environmentalContrast = story.environmental_contrast || story.visual_distinction || "The left is quiet and sparse; the right feels warmer through shared interaction.";
  const product = story.brand_categories?.[0] ?? "";
  const executionRisks = story.execution_risks?.length
    ? story.execution_risks
    : ["Keep both characters grounded and unobscured by props.", "Preserve equal body size and every locked character feature."];

  return {
    form: {
      format: story.format || "x-with-you",
      leftTitle: titles.left,
      rightTitle: titles.right,
      leftCharacter,
      category: story.category,
      theme: story.category.toLowerCase(),
      emotionalInsight: story.concept,
      leftCharacterAction: leftAction,
      leftSetting,
      leftProps,
      leftEmotion,
      rightCharacterActions: rightActions,
      rightSetting,
      rightProps,
      rightEmotion,
      sharedEnvironment,
      environmentalContrast,
      background: story.background_color || "warm cream",
      accentColor: story.accent_color || "muted mustard",
      cameraAngle: story.camera_angle || legacyCamera(story),
      brandFriendly: Boolean(story.brand_friendly),
      productCategory: product,
      naturalProductPlacement: product ? `Replace one existing ${product} prop without changing the story.` : "",
      executionRisks,
      notes: story.notes || `Story Library seed: ${story.title}.`,
    },
    props: [...new Set([...leftProps, ...rightProps])],
    executionRisks,
    brandPlacementOpportunities: product ? [`A natural ${product} prop already required by the scene.`] : [],
    novelAngle: environmentalContrast,
    whySomeoneWouldShare: `It turns ${story.concept.toLowerCase()} into a recognizable “that reminds me of us” moment.`,
  };
}
