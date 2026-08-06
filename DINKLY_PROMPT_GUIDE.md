# DINKLY Prompt Guide

This is the standing specification for future DINKLY comic prompts.

## Knowledge-base priority

Before creating a comic, read this guide together with [`brain/DINKLY_BRAND_BIBLE_v1.0.md`](brain/DINKLY_BRAND_BIBLE_v1.0.md) and inspect [`references/dinkly_young.png`](references/dinkly_young.png).

- Use the reference image as the absolute source of truth for character appearance.
- Use this Prompt Guide for current production mechanics and approved rule amendments.
- Use the Brand Bible for mission, tone, emotional intent, story selection, and licensing fit.
- When an older example conflicts with a newer production rule, use the newer and more specific production rule while preserving the brand's emotional North Star.

## Brand idea

DINKLY makes ordinary moments feel better because they are shared. Comics should communicate this emotionally in under two seconds, without dialogue or a complex story.

Use the comparison formula:

`X` / `X WITH YOU`

The activity changes as little as possible. The emotional feeling changes.

## Character reference

Use [`references/dinkly_young.png`](references/dinkly_young.png) as the authoritative production-model reference.

- Dinka is the girl on the left of the reference: ponytail, red bow, and eyelashes.
- Dinko is the boy on the right of the reference: exactly two hair tufts and no bow or ponytail.
- Keep Dinka and Dinko at the same body size and scale.
- Preserve their exact round proportions, yellow color, orange spots, black oval eyes with white highlights, facial construction, thick black outlines, tiny nub arms, and tiny nub feet.
- Never add long limbs, fingers, human hands, human anatomy, shoes, clothing, extra hair, alternate eyes, missing features, altered spot patterns, or off-model expressions.

## Emotional contrast

- The character in the left scene must look sad, bored, or neutral. The character must never look happy or smile.
- Keep the left emotion restrained rather than melodramatic; no tears unless a future concept explicitly requires them.
- The right scene should show immediate warmth, comfort, or happiness from being together.

## Composition

- Square 1:1 canvas.
- Two equal side-by-side scenes.
- Use one uninterrupted, flat pastel fill across the entire canvas so both sides have exactly the same color and shade.
- Add a thin solid black vertical divider at the exact horizontal center. It should be approximately half the canvas height and vertically centered, running roughly from 25% to 75% of the image height.
- The divider must not touch the top, bottom, characters, or captions.
- Use ample breathing room and keep the characters as the focal point.
- Rotate camera framing across future concepts when appropriate, but keep comparison scenes visually coherent.

## Typography

- Place both captions at the bottom of the comic, beneath their corresponding scenes.
- Use **Bubblebody Neue Regular** only.
- Use solid black text with no outline, shadow, gradient, or decorative effect.
- Center each caption horizontally within its half.
- Keep both captions on the same baseline, at the same font size and weight.
- Spell the requested captions exactly and add no other text.
- Write target captions as plain standalone lines inside production prompts. Never surround them with quotation marks, smart quotes, apostrophes, brackets, or code formatting.
- Do not repeat target captions inside quotation marks in the quality check, because the image model may reproduce those marks.
- Unless a future request explicitly requires punctuation, render captions without terminal periods.

## Props

- Build a recognizable but minimalist environment with three to five relevant prop types rather than relying on tiny decorative symbols.
- Prefer meaningful scene-setting objects such as chairs, tables, counters, lamps, shelves, coffee machines, laundry baskets, beds, sofas, or shopping carts when they naturally fit the activity.
- Do not use generic filler such as scattered coffee beans, dots, sparkles, or unrelated decorations as the primary scene props.
- Repeat the same environmental setup on both sides as closely as possible so the emotional contrast comes from being alone versus being together, not from receiving a better location.
- Simplify every environmental object into a clean, rounded flat-vector silhouette. The scene should feel complete but never realistic, detailed, or busy.
- Every prop should use one flat fill color only, plus an optional black outline. Avoid internal detail, patterns, gradients, highlights, and texture.
- Prop colors should be muted and tonal, blending with the pastel background. Use no more than one restrained accent color across the scene.
- Furniture may be large enough to establish the environment but must never dwarf, hide, crop, or overpower the characters.
- Keep all props grounded and secondary to the characters. Do not allow objects to float, overlap the characters, cross the divider, or interfere with the captions.

## Visual style

- Official DINKLY flat-vector appearance.
- Matte colors, rounded shapes, and thick smooth black character outlines.
- No gradients, textures, realism, painterly rendering, 3D effects, complex scenery, detailed interiors, shadows, or busy color palettes.
- Never use a white background.

## Required prompt structure

Every production prompt must include:

1. REFERENCE PRIORITY
2. LAYOUT
3. LEFT PANEL
4. RIGHT PANEL
5. PROP DIRECTION
6. TYPOGRAPHY
7. CHARACTER LOCK
8. STYLE
9. QUALITY CHECK

The quality check must explicitly verify character identity, model accuracy, equal scale, left-side non-happy emotion, right-side warmth, one identical background fill, correct half-height divider, correct bottom typography, a coherent minimalist environment repeated across both sides, restrained prop colors, immediate emotional clarity, and official DINKLY brand fit.
