# Nano Banana Production Rules

## Objective

Write concise, scene-specific prompts that prioritize locked character accuracy and emotional clarity over environmental detail. Do not paste the full brand system into every generation.

## Required split-comic structure

1. REFERENCE PRIORITY
2. LAYOUT
3. LEFT PANEL
4. RIGHT PANEL
5. CHARACTER LOCK
6. STYLE
7. FINAL QUALITY CHECK

Add PROP DIRECTION, BACKGROUND, TEXT, or BRAND REFERENCE sections only when the scene requires them.

## Required single-panel structure

1. REFERENCE PRIORITY
2. COMPOSITION
3. SCENE
4. CHARACTER LOCK
5. BACKGROUND
6. TEXT
7. STYLE
8. FINAL QUALITY CHECK

## Reference priority

Name each reference and its purpose. Character model sheets always have highest priority for character appearance.

```text
Use references/dinkly_young.png only for Dinka and Dinko's identity, proportions, markings, colors, eyes, hair, bow, ponytail, outline, and anatomy. Use the product reference only for packaging. Do not transfer the product reference's style into the characters.
```

## Scene construction rules

- Give each character one clear action.
- Avoid simultaneous conflicting actions.
- Describe who is left, right, foreground, background, seated, or standing.
- State the correct support surface when furniture is involved.
- Keep characters on the floor unless explicitly seated on a visible chair, sofa, or bed surface.
- Explicitly prohibit standing or sitting on tables, counters, carts, shelves, vanities, and kitchen islands when those objects appear.
- Use three to five relevant prop types, not decorative filler.
- Repeat the environment across split panels so the emotional contrast—not a better setting—creates warmth.

## Relative scale language

Size objects relative to the character or full canvas.

Good:

```text
The phone is approximately the size of Dinko's face and occupies no more than 8–10% of the full illustration.
```

Avoid ambiguous words such as `tiny`, `human-sized`, `normal`, or `large` when scale matters.

For mugs, toothbrushes, phones, branded packaging, flowers, and travel objects, state a relative size and maximum canvas percentage when distortion risk is known.

## Character-lock selection

Include the full character lock only when generating both characters from scratch. For narrow edit prompts, include only the rules relevant to the error being repaired plus a statement that all other character features must remain unchanged.

Always protect:

- Same body size and round proportions
- Dinko's exactly two hair tufts
- Dinka's red bow and connected ponytail
- Black oval eyes with white highlights
- Tiny nub arms and feet
- No visible legs, hands, fingers, clothing, shoes, or human anatomy

## Background and text

- Use one continuous pastel background in split comics.
- Do not describe separate left and right background fills unless intentionally different.
- Protect the bottom caption zone.
- Render only supplied text.
- Do not add quotation marks, extra punctuation, or replacement lettering.
- Use Bubblebody Neue Regular for the standard pastel comic system.

## Failure-prevention selection

Read `FAILURES.md` and include prevention language only for risks present in the current scene.

- Furniture scene: protect seat placement and forbid tabletops.
- Shopping scene: keep characters beside the cart and on the floor.
- Phone scene: define scale, count, clarity, and ownership.
- Product scene: separate reference purposes and consider placeholder-first production.

## Image-editing rules

An edit prompt must state:

1. What remains unchanged
2. The exact region to edit
3. The exact error to fix
4. The required corrected placement or appearance
5. What must not be introduced

```text
Edit only the right panel. Leave the left panel, text, background, colors, furniture, and props unchanged. Move both characters off the tabletop and place each round body directly on a visible chair seat. Preserve their exact size, eyes, markings, bow, ponytail, and two-hair-tuft design. Do not add legs, hands, fingers, clothing, or new objects.
```

Recommend regeneration when the underlying composition is structurally wrong, character identity has drifted across the full image, or two precise edit attempts have failed.

## Prompt-bloat test

Remove an instruction when it does not affect character identity, scene action, spatial placement, emotional contrast, current failure risk, required text, or brand accuracy.

If the model must prioritize dozens of unrelated prohibitions, simplify the scene instead.
