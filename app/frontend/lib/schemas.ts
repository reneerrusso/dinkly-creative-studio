import { z } from "zod";

export const conceptSchema = z.object({
  format: z.string().min(1, "Choose a format"),
  leftTitle: z.string().min(1, "Add the left title").max(90),
  rightTitle: z.string().min(1, "Add the right title").max(90),
  leftCharacter: z.enum(["boy", "girl"]),
  category: z.string().min(1, "Add a category"),
  theme: z.string().min(1, "Add an emotional theme"),
  emotionalInsight: z.string().min(8, "Name the emotional truth"),
  leftCharacterAction: z.string().min(3, "Describe one visible action"),
  leftSetting: z.string().min(3, "Define the left-panel setting"),
  leftProps: z.array(z.string().min(1)),
  leftEmotion: z.string().min(3, "Describe the left emotion"),
  rightCharacterActions: z.string().min(3, "Describe the visible shared action"),
  rightSetting: z.string().min(3, "Define the right-panel setting"),
  rightProps: z.array(z.string().min(1)),
  rightEmotion: z.string().min(3, "Describe the right emotion"),
  sharedEnvironment: z.string().min(3, "Describe what visually remains consistent"),
  environmentalContrast: z.string().min(3, "Describe the visible emotional contrast"),
  background: z.string().min(1),
  accentColor: z.string().min(1),
  cameraAngle: z.string().min(1),
  brandFriendly: z.boolean(),
  productCategory: z.string().optional(),
  naturalProductPlacement: z.string().optional(),
  executionRisks: z.array(z.string().min(1)),
  notes: z.string().optional(),
});

export type ConceptFormValues = z.infer<typeof conceptSchema>;

const optionalMetric = z.preprocess(
  (value) => (value === "" || value === undefined ? null : Number(value)),
  z.number().int().nonnegative().nullable(),
);

export const socialPostSchema = z.object({
  title: z.string().min(1, "A working title is required"),
  platform: z.string().nullable().optional(),
  postDate: z.string().nullable().optional(),
  views: optionalMetric,
  shares: optionalMetric,
  likes: optionalMetric,
  comments: optionalMetric,
  saves: optionalMetric,
  format: z.string().nullable().optional(),
  storyline: z.string().nullable().optional(),
  emotionalTheme: z.string().nullable().optional(),
  leftPanelSummary: z.string().nullable().optional(),
  rightPanelSummary: z.string().nullable().optional(),
  backgroundColor: z.string().nullable().optional(),
  accentColor: z.string().nullable().optional(),
  cameraAngle: z.string().nullable().optional(),
  props: z.string().nullable().optional(),
  brandIntegration: z.string().nullable().optional(),
  uploadedAssetReference: z.string().nullable().optional(),
  uploadedAssetHash: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
});

export type SocialPostFormInput = z.input<typeof socialPostSchema>;
export type SocialPostFormValues = z.output<typeof socialPostSchema>;

export const spriteAnimationSchema = z.object({
  characterId: z.string().min(1, "Choose a character or asset group"),
  name: z.string().min(2, "Name the animation"),
  category: z.enum(["idle", "facial", "movement", "emotion", "interaction", "prop_action", "sleep", "celebration", "shared", "environmental"]),
  description: z.string().max(500).default(""),
  frameRate: z.coerce.number().min(1).max(60),
  loopMode: z.enum(["loop", "ping_pong", "play_once", "hold_last"]),
  expectedFrameCount: z.coerce.number().int().min(1).max(120),
  defaultAnchorX: z.coerce.number().min(0).max(1),
  defaultAnchorY: z.coerce.number().min(0).max(1),
  tags: z.string().default(""),
  notes: z.string().default(""),
});

export type SpriteAnimationFormValues = z.infer<typeof spriteAnimationSchema>;
