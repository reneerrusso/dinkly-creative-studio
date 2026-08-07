# DINKLY Sprite Animation Guide

## Motion philosophy

DINKLY motion is small, expressive, and emotionally readable. One animation communicates one action. Character consistency is more important than mechanical smoothness or frame count.

Fewer frames are often better. A held pose, delayed blink, tiny lean, or gentle prop movement can create more charm than constant motion.

## Practical frame counts

- Blink: 3–4 frames
- Idle breathing: 4–6 frames
- Happy bounce: 5–7 frames
- Wave: 6–8 frames
- Walk: 6–8 frames
- Laugh: 5–7 frames
- Coffee sip: 6–8 frames
- Hug: 4–6 coordinated frames
- Dance: 8–12 frames
- Environmental loops: 4–12 frames

Do not force an animation to meet the top of a range. Add a frame only when it clarifies timing or silhouette.

## Character motion

Preserve the round body. Avoid squash-and-stretch, rubber limbs, independent horizontal or vertical scaling, realistic weight shifts, human walking mechanics, knees, elbows, fingers, or long steps.

Use slight whole-body translation or rotation, tiny nub movement, eye changes, mouth changes, prop changes, and carefully controlled hair, ponytail, or bow follow-through.

Avoid excessive bouncing. A happy bounce is one specific state, not the default behavior for every positive scene.

## Natural loops

The final frame should flow into the first without a visible jump. Ping pong works for breathing, looking, subtle sways, and environmental effects. Loop works for continuous cycles. Play once works for gestures. Hold last works for waves, kisses, high fives, and completed prop actions.

First- and last-frame holds can slow an action without adding redundant art.

## Shared interaction timing

Shared interactions use a coordinated canvas, frame rate, duration, and relative anchors. Review both characters together. Dinko and Dinka should contact the intended point on the same frame and remain equal in scale.

Never construct a shared hug by independently looping two unrelated hug animations. Pair deliberately authored sets and review the combined preview.

## Props and effects

Props keep realistic scale relative to the round bodies. Environmental effects may use larger transparent canvases, but should not cover faces or obscure character identity. One effect loop should communicate one effect: steam, rain, snow, hearts, sparkles, or leaves.

## Review order

1. Confirm identity on every frame.
2. Confirm uniform scale and canvas dimensions.
3. Align anchors and floor contact.
4. Check the main action in sequence.
5. Check the loop seam and holds.
6. Check props and effects at final scene scale.
7. Approve frames, then approve the animation.

