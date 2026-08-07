#!/usr/bin/env python3
"""Pillow worker for safe DINKLY sprite inspection, slicing, preview, and export."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def _open(path: str) -> Image.Image:
    image = Image.open(path)
    image.load()
    return image


def inspect(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    with _open(str(path)) as image:
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        minimum, maximum = alpha.getextrema()
        return {
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "format": image.format,
            "transparent": minimum < 255,
            "fully_transparent": maximum == 0,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }


def thumbnail(payload: dict[str, Any]) -> dict[str, Any]:
    output = Path(payload["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with _open(payload["path"]) as source:
        image = source.convert("RGBA")
        image.thumbnail((int(payload.get("max_width", 320)), int(payload.get("max_height", 320))), Image.Resampling.LANCZOS)
        image.save(output, "PNG")
    return {"path": str(output), "width": image.width, "height": image.height}


def slice_sheet(payload: dict[str, Any]) -> dict[str, Any]:
    frame_width = int(payload["frame_width"])
    frame_height = int(payload["frame_height"])
    rows = int(payload["rows"])
    columns = int(payload["columns"])
    requested_cells = payload.get("selected_cells")
    selected = list(range(rows * columns)) if requested_cells is None else [int(cell) for cell in requested_cells]
    if not selected:
        raise ValueError("Select at least one sprite-sheet cell")
    if len(selected) != len(set(selected)):
        raise ValueError("Selected sprite-sheet cells must not contain duplicates")
    output_dir = Path(payload["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    with _open(payload["path"]) as source:
        image = source.convert("RGBA")
        if frame_width * columns > image.width or frame_height * rows > image.height:
            raise ValueError("Slicing grid exceeds the supplied sprite sheet dimensions")
        for order, cell in enumerate(selected):
            cell = int(cell)
            row, column = divmod(cell, columns)
            if cell < 0 or row >= rows:
                raise ValueError(f"Selected cell {cell} is outside the declared grid")
            frame = image.crop(
                (
                    column * frame_width,
                    row * frame_height,
                    (column + 1) * frame_width,
                    (row + 1) * frame_height,
                )
            )
            target = output_dir / f"frame-{order + 1:04d}.png"
            if target.exists():
                raise FileExistsError(f"Refusing to overwrite {target.name}")
            frame.save(target, "PNG")
            paths.append(str(target))
    return {"paths": paths, "frame_count": len(paths)}


def _next_power_of_two(value: int) -> int:
    return 1 if value <= 1 else 2 ** math.ceil(math.log2(value))


def export_sheet(payload: dict[str, Any]) -> dict[str, Any]:
    frame_paths = [str(path) for path in payload["frame_paths"]]
    if not frame_paths:
        raise ValueError("At least one frame is required")
    images = [_open(path).convert("RGBA") for path in frame_paths]
    try:
        frame_width = max(image.width for image in images)
        frame_height = max(image.height for image in images)
        padding = int(payload.get("padding", 2))
        layout = payload.get("layout", "horizontal")
        if layout == "horizontal":
            columns, rows = len(images), 1
        elif layout == "vertical":
            columns, rows = 1, len(images)
        else:
            columns = int(payload.get("columns") or math.ceil(math.sqrt(len(images))))
            rows = math.ceil(len(images) / columns)
        cell_width = frame_width + padding * 2
        cell_height = frame_height + padding * 2
        sheet_width = columns * cell_width
        sheet_height = rows * cell_height
        if payload.get("power_of_two"):
            sheet_width = _next_power_of_two(sheet_width)
            sheet_height = _next_power_of_two(sheet_height)
        sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))
        cells: list[dict[str, int]] = []
        for index, image in enumerate(images):
            row, column = divmod(index, columns)
            x = column * cell_width + padding + (frame_width - image.width) // 2
            y = row * cell_height + padding + (frame_height - image.height)
            sheet.alpha_composite(image, (x, y))
            cells.append({"index": index, "x": column * cell_width, "y": row * cell_height, "width": cell_width, "height": cell_height})
        output = Path(payload["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite {output.name}")
        sheet.save(output, "PNG")
        return {
            "path": str(output),
            "frame_width": frame_width,
            "frame_height": frame_height,
            "sheet_width": sheet_width,
            "sheet_height": sheet_height,
            "columns": columns,
            "rows": rows,
            "cells": cells,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        }
    finally:
        for image in images:
            image.close()


def export_animation(payload: dict[str, Any]) -> dict[str, Any]:
    images = [_open(str(path)).convert("RGBA") for path in payload["frame_paths"]]
    try:
        output = Path(payload["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite {output.name}")
        durations = [int(value) for value in payload["durations"]]
        format_name = str(payload["format"]).upper()
        save_images = images[1:]
        images[0].save(
            output,
            format=format_name,
            save_all=True,
            append_images=save_images,
            duration=durations,
            loop=0 if payload.get("loop", True) else 1,
            disposal=2,
            lossless=True,
        )
        return {"path": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    finally:
        for image in images:
            image.close()


def technical_samples(payload: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(payload["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    eye_heights = [26, 5, 26]
    for index, eye_height in enumerate(eye_heights, start=1):
        target = output_dir / f"technical-blink-{index:02d}.png"
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite {target.name}")
        image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((46, 32, 210, 204), fill=(188, 188, 178, 255), outline=(25, 25, 23, 255), width=6)
        draw.ellipse((82, 90, 108, 90 + eye_height), fill=(25, 25, 23, 255))
        draw.ellipse((148, 90, 174, 90 + eye_height), fill=(25, 25, 23, 255))
        draw.line((68, 207, 188, 207), fill=(154, 77, 43, 255), width=4)
        label = f"TECHNICAL SAMPLE {index} - NOT OFFICIAL"
        font = ImageFont.load_default()
        box = draw.textbbox((0, 0), label, font=font)
        draw.rectangle((8, 228, 248, 250), fill=(247, 244, 236, 235))
        draw.text(((256 - (box[2] - box[0])) / 2, 235), label, fill=(45, 45, 42, 255), font=font)
        image.save(target, "PNG")
        paths.append(str(target))
    return {"paths": paths, "label": "TECHNICAL SAMPLE - NOT OFFICIAL"}


OPERATIONS = {
    "inspect": inspect,
    "thumbnail": thumbnail,
    "slice": slice_sheet,
    "sheet": export_sheet,
    "animation": export_animation,
    "technical_samples": technical_samples,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=sorted(OPERATIONS))
    args = parser.parse_args()
    payload = json.loads(input())
    result = OPERATIONS[args.operation](payload)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
