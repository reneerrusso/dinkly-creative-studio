# DINKLY Sprite Export Guide

## Export principles

Exports are immutable local production records. Every export receives a unique directory and metadata file. Existing frames, sheets, code helpers, metadata, and prior exports are never overwritten.

Draft animations can be exported for testing, but the export is labeled **Draft — not approved for production use**. Technical samples can never become official assets.

## Image formats

### Horizontal sprite strip

All frames appear left to right in one row. This is the default for CSS steps and simple Canvas runtimes.

### Vertical sprite strip

All frames appear top to bottom in one column.

### Grid sprite sheet

Frames are packed into rows and columns. Choose this for compact runtime atlases.

### Individual PNG frames

Creates a numbered frame directory. Source artwork is copied; originals remain untouched.

### Animated GIF and WEBP

Frame durations and loop behavior are preserved. GIF is widely compatible; WEBP usually preserves transparency and color more efficiently.

## Padding

Available transparent padding is 0, 2, 4, or 8 pixels. The default is 2 pixels. Padding reduces texture bleeding in runtime atlases. Optional power-of-two sizing expands the transparent sheet canvas without scaling any frame.

## Metadata JSON

Every image export includes animation name, character, frame dimensions, frame count, frame rate, loop mode, anchor, padding, frame durations, offsets, and cell coordinates. The `approved` and `technicalSample` fields prevent draft assets from being mistaken for official production art.

## Runtime exports

- **Generic JSON:** portable timing, anchor, and frame data.
- **CSS steps:** a concise steps-based background animation scaffold.
- **React component:** a duration-aware frame component.
- **Remotion asset:** a manifest for use in final MP4 compositions.
- **Canvas helper:** a small runtime drawing function and frame data.

These helpers are intentionally engine-neutral. Version one does not generate Phaser, Unity, Godot, or other game-engine packages.

## Motion Studio handoff

Motion Studio receives an animation or composition identifier. Composer generates a Remotion-ready manifest with the canvas, background, layer order, animation records, positions, uniform scales, start offsets, and warnings. MP4 rendering requires the optional Remotion runtime and is separate from sprite validation.

## Generic metadata example

```json
{
  "name": "dinko-blink",
  "frameRate": 8,
  "loop": true,
  "anchor": { "x": 0.5, "y": 1 },
  "frames": [
    {
      "x": 0,
      "y": 0,
      "width": 256,
      "height": 256,
      "durationMs": 120
    }
  ]
}
```

