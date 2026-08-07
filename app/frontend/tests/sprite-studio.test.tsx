import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import MotionStudioPage from "@/app/motion-studio/page";
import { AnimationControls } from "@/components/sprite-studio/animation-controls";
import { ExportDialog } from "@/components/sprite-studio/export-dialog";
import { FrameDropzone } from "@/components/sprite-studio/frame-dropzone";
import { FrameTimeline } from "@/components/sprite-studio/frame-timeline";
import { LayerComposer } from "@/components/sprite-studio/layer-composer";
import { LoopSettings } from "@/components/sprite-studio/loop-settings";
import { SpriteLibrary } from "@/components/sprite-studio/sprite-library";
import { ValidationPanel } from "@/components/sprite-studio/validation-panel";
import { spriteAnimationSchema } from "@/lib/schemas";
import type { SpriteAnimation, SpriteCharacter } from "@/lib/types";

const character: SpriteCharacter = { id: "sprite-character-dinko", name: "Dinko", slug: "dinko", character_type: "dinko", official_reference_paths: ["references/dinkly_young.png"], default_canvas_width: 256, default_canvas_height: 256, default_anchor_x: 0.5, default_anchor_y: 1, default_frame_rate: 8, approved: true, locked: true, notes: "Locked" };
const animation: SpriteAnimation = { id: "sprite-animation-dinko-blink", name: "Blink", slug: "dinko-blink", character_id: character.id, character, category: "facial", description: "Subtle blink", frames: [], frame_ids: [], frame_count: 0, frame_rate: 8, duration_ms: 0, loop: true, loop_mode: "loop", hold_first_frame_ms: 0, hold_last_frame_ms: 0, default_scale: 1, expected_frame_count: 4, default_anchor_x: 0.5, default_anchor_y: 1, approved: false, approval_level: "Draft", tags: ["blink"], required_layers: [], optional_layers: [], thumbnail_path: null, preview_path: null, status: "Frames needed", validation_status: "Frames needed", validation_checklist: ["Exactly two hair tufts", "No visible legs"], technical_sample: false, notes: "Frames needed" };
const frame = { id: "frame-1", character_id: character.id, animation_id: animation.id, frame_index: 0, image_path: "frame.png", asset_url: "/sprite-assets/frame.png", width: 256, height: 256, duration_ms: 125, anchor_x: 0.5, anchor_y: 1, offset_x: 0, offset_y: 0, opacity: 1, approved: false, validation_status: "valid" as const, validation_warnings: [], review_status: "Not reviewed" as const, review_notes: "", transparent: true };

describe("Sprite Studio", () => {
  it("filters the motion library by character and search", async () => {
    const user = userEvent.setup();
    render(<SpriteLibrary animations={[animation]} characters={[character]}/>);
    expect(screen.getByText("Blink")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("Search motions…"), "dance");
    expect(screen.queryByText("Blink")).not.toBeInTheDocument();
  });

  it("accepts transparent frame files in the upload control", () => {
    const onFiles = vi.fn();
    const { container } = render(<FrameDropzone onFiles={onFiles}/>);
    const input = container.querySelector("input[type=file]") as HTMLInputElement;
    const frame = new File(["frame"], "frame.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [frame] } });
    expect(onFiles).toHaveBeenCalledWith([frame]);
  });

  it("changes loop mode without adding a heavy timeline", async () => {
    const user = userEvent.setup();
    const onLoopMode = vi.fn();
    render(<LoopSettings loopMode="loop" onLoopMode={onLoopMode} frameRate={8} onFrameRate={vi.fn()} holdFirst={0} holdLast={0} onHoldFirst={vi.fn()} onHoldLast={vi.fn()}/>);
    await user.selectOptions(screen.getByTestId("loop-selection"), "ping_pong");
    expect(onLoopMode).toHaveBeenCalledWith("ping_pong");
  });

  it("exposes preview playback controls", async () => {
    const user = userEvent.setup();
    const onPlayPause = vi.fn();
    const onNext = vi.fn();
    const onSpeed = vi.fn();
    render(<AnimationControls playing={false} onPlayPause={onPlayPause} onRestart={vi.fn()} onPrevious={vi.fn()} onNext={onNext} speed={1} onSpeed={onSpeed} loop onLoop={vi.fn()}/>);
    await user.click(screen.getByRole("button", { name: "Play" }));
    await user.click(screen.getByRole("button", { name: "Next frame" }));
    await user.selectOptions(screen.getByLabelText("Playback speed"), "1.5");
    expect(onPlayPause).toHaveBeenCalledOnce();
    expect(onNext).toHaveBeenCalledOnce();
    expect(onSpeed).toHaveBeenCalledWith(1.5);
  });

  it("reorders frames through the simple drag timeline", () => {
    const onReorder = vi.fn();
    const frames = [frame, { ...frame, id: "frame-2", frame_index: 1 }];
    render(<FrameTimeline frames={frames} selectedIds={[]} onSelect={vi.fn()} onReorder={onReorder} onRemove={vi.fn()}/>);
    const items = Array.from(screen.getByTestId("frame-timeline").children);
    fireEvent.dragStart(items[0]);
    fireEvent.drop(items[1]);
    expect(onReorder).toHaveBeenCalledWith(["frame-2", "frame-1"]);
  });

  it("shows identity checks and keeps approval disabled with no frames", () => {
    render(<ValidationPanel animation={animation} onValidate={vi.fn()} onApprove={vi.fn()}/>);
    expect(screen.getByText("Exactly two hair tufts")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve animation" })).toBeDisabled();
  });

  it("adds a Composer layer", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<LayerComposer layers={[]} animations={[animation]} onChange={onChange}/>);
    await user.click(screen.getByRole("button", { name: "Add layer" }));
    expect(onChange).toHaveBeenCalledWith([expect.objectContaining({ layer_type: "effect", scale: 1 })]);
  });

  it("submits an explicit sprite-sheet export format", async () => {
    const user = userEvent.setup();
    const onExport = vi.fn();
    const ready = { ...animation, frames: [frame], frame_ids: [frame.id], frame_count: 1, duration_ms: 125, status: "Draft" as const };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({ ok: true, json: async () => ({ export: { id: "export-1" } }) } as Response);
    render(<ExportDialog animation={ready} onExport={onExport}/>);
    await user.click(screen.getByRole("button", { name: "Export" }));
    await user.selectOptions(screen.getByTestId("sprite-export-format"), "metadata_json");
    await user.click(screen.getByRole("button", { name: "Create export" }));
    expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/sprite-sheets/export"), expect.objectContaining({ method: "POST" }));
    expect(onExport).toHaveBeenCalled();
  });

  it("opens the approved Sprite Library workflow in Motion Studio", async () => {
    const user = userEvent.setup();
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({ ok: true, json: async () => [] } as Response);
    render(<MotionStudioPage/>);
    await user.click(screen.getAllByRole("button", { name: "Choose workflow" })[0]);
    expect(await screen.findByText("Approved Sprite Library")).toBeInTheDocument();
    expect(screen.getByText("Finish frame review to make animations available across the studio.")).toBeInTheDocument();
  });

  it("validates the new animation form contract", () => {
    const result = spriteAnimationSchema.safeParse({ characterId: character.id, name: "Blink", category: "facial", description: "", frameRate: 8, loopMode: "loop", expectedFrameCount: 4, defaultAnchorX: 0.5, defaultAnchorY: 1, tags: "blink", notes: "" });
    expect(result.success).toBe(true);
  });
});
