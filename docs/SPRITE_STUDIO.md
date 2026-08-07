# DINKLY Sprite Studio

## Purpose

DINKLY Sprite Studio is the local production library for small, reusable, frame-by-frame motion. It keeps approved artwork stable: the system never regenerates Dinko or Dinka between frames and never treats technical samples as official character art.

Use Sprite Studio for animated comics, social videos, website mascots, GIFs, stickers, game-ready sheets, and future interactive experiences. The preferred motion is subtle, readable, and easy to reuse.

## Core workflow

1. Open **Sprite Studio** and choose a locked character or managed asset group.
2. Create one animation definition for one action, such as Blink, Coffee sip, or Floating hearts.
3. Upload approved transparent PNG or WEBP frames, or import a prebuilt sprite sheet.
4. Arrange frames, set timing, and preview the loop.
5. Align anchors to bottom center and inspect canvas, scale, crop, and floor consistency.
6. Review every frame with the identity checklist. Mark each frame Pass, Needs edit, or Reject.
7. Run automatic validation and approve the animation only after every frame passes.
8. Export a sheet, animated asset, metadata file, or runtime helper.
9. Send approved motion to Sprite Composer or Motion Studio.

## Creating an animation

Choose Dinko, Dinka, Shared actions, Props, or Environmental effects. Add a concise name, category, expected frame count, frame rate, loop mode, bottom-center anchor, tags, and illustrator notes. Definitions may exist before artwork and are visibly labeled **Frames needed**.

Recommended starting rates are 8 fps with four to eight frames. Dance and environmental loops can use more when the action genuinely needs them.

## Uploading frames

Individual frame uploads accept PNG and WEBP. Character and prop frames require transparency. The studio checks file type, local size limit, readability, duplicate content, transparency, consistent dimensions, safe filenames, and repository-safe paths.

Every upload receives a unique filename. Existing files are never overwritten.

## Importing a sprite sheet

Open an animation and choose **Sprite sheet** under Add frames. Supply frame width, frame height, row count, and column count. The preview grid allows unused cells to be deselected and the selected-cell order becomes the frame order. Keep **Require transparent background** enabled for character, prop, and transparent-effect sheets. Extraction rejects empty, duplicate, and out-of-range selections, creates unique new frames, and refuses to overwrite existing files.

## Timeline and timing

Drag frames horizontally to reorder them. Shift-click to select several frames, then apply one duration. Duplicate a frame when a deliberate hold is needed; the duplicated timing record safely shares the same local artwork file. Remove is explicit and preserves recoverable local source files.

Loop modes are Loop, Ping pong, Play once, and Hold last. The selected frame can be marked as the loop start or loop end, and the live preview immediately shows that range. First- and last-frame holds can make small actions feel intentional without inventing extra artwork.

## Alignment and onion skin

Anchors use normalized coordinates from 0 to 1. Character defaults are `x: 0.5`, `y: 1`, or bottom center. This locks nub feet to the floor line. Align all frames to the selected frame or restore all frames to bottom center.

Onion skin is optional and off by default. It overlays the previous and next frames only for alignment; Sprite Studio does not include drawing tools.

## Character validation

Automatic validation covers transparency, dimensions, normalized anchors, canvas consistency, large vertical offsets, and possible floor drift. Manual validation protects character identity, proportions, eyes, orange spots, outline, mouth, arms, feet, hair, bow, ponytail, scale, anatomy, artifacts, and cropping.

Dinko review always includes exactly two hair tufts. Dinka review always includes the exact bright red bow and connected ponytail.

## Approval levels

- **Draft:** definition or early frame work.
- **Frame review:** individual frames are being checked.
- **Animation review:** the full loop is ready for review.
- **Approved:** every frame passed and the loop is cleared for reuse.
- **Deprecated:** retained for history but unavailable in production selectors.

Only approved animation records appear by default in Composer and production handoffs. Drafts can be revealed with an explicit filter.

## Shared actions

Hugs, hand-holding, cuddles, dances, and kisses are coordinated sets. A shared interaction connects one Dinko animation and one Dinka animation with one frame rate, duration, loop mode, and relative offsets. Both source animations must be approved before the shared interaction can be approved.

Do not scale one character larger than the other. A Composer scale mismatch produces a warning.

## Motion Studio

The **Use in Motion Studio** action sends the animation or composition identifier into the handoff. Motion Studio supports flat comic animation, approved sprite animation, or a controlled mix. Sprite Studio creates a Remotion-ready manifest; MP4 generation is an optional rendering stage and never uses generative video by default.

## Technical samples

Technical samples may use simple labeled shapes to test upload, transparency, timing, slicing, and export. They must include **TECHNICAL SAMPLE — NOT OFFICIAL**, remain unapproved, and never appear as official DINKLY character artwork.
