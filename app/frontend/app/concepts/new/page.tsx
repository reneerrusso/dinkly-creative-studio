"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, CheckCircle2, Loader2, Plus, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { accentColors, backgroundFamilies, promptFormats } from "@/lib/constants";
import { conceptSchema, type ConceptFormValues } from "@/lib/schemas";
import { developStorySeed, type DevelopedStorySeed, type StorySeed } from "@/lib/story-seed";
import type { Concept, Score } from "@/lib/types";

const emptyDefaults: ConceptFormValues = {
  format: "x-with-you",
  leftTitle: "",
  rightTitle: "",
  leftCharacter: "boy",
  category: "Everyday routines",
  theme: "companionship",
  emotionalInsight: "",
  leftCharacterAction: "",
  leftSetting: "",
  leftProps: [],
  leftEmotion: "Neutral, bored, or gently sad—never happy.",
  rightCharacterActions: "",
  rightSetting: "",
  rightProps: [],
  rightEmotion: "Warm and connected because the ordinary moment is shared.",
  sharedEnvironment: "",
  environmentalContrast: "",
  background: "warm cream",
  accentColor: "muted mustard",
  cameraAngle: "medium straight-on",
  brandFriendly: false,
  productCategory: "",
  naturalProductPlacement: "",
  executionRisks: [],
  notes: "",
};

export default function NewConceptPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-muted">Loading Story Library seed…</div>}>
      <NewConcept />
    </Suspense>
  );
}

function NewConcept() {
  const router = useRouter();
  const params = useSearchParams();
  const storyId = params.get("story");
  const [story, setStory] = useState<StorySeed>();
  const [developed, setDeveloped] = useState<DevelopedStorySeed>();
  const [seedLoading, setSeedLoading] = useState(Boolean(storyId));
  const [seedError, setSeedError] = useState("");
  const {
    register,
    reset,
    handleSubmit,
    control,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<ConceptFormValues>({ resolver: zodResolver(conceptSchema), defaultValues: emptyDefaults });

  const leftCharacter = watch("leftCharacter");
  const leftProps = watch("leftProps");
  const rightProps = watch("rightProps");

  useEffect(() => {
    if (!storyId) return;
    setSeedLoading(true);
    api<StorySeed>(`/api/story-library/${encodeURIComponent(storyId)}`)
      .then((record) => {
        const draft = developStorySeed(record);
        setStory(record);
        setDeveloped(draft);
        reset(draft.form);
        setSeedError("");
      })
      .catch((error) => setSeedError(error instanceof Error ? error.message : "Could not load Story Library seed"))
      .finally(() => setSeedLoading(false));
  }, [reset, storyId]);

  async function submit(values: ConceptFormValues) {
    const leftName = values.leftCharacter === "girl" ? "Girl DINKLY" : "Boy DINKLY";
    const leftScene = `${leftName} ${values.leftCharacterAction}. Setting: ${values.leftSetting}. Purposeful props: ${values.leftProps.join(", ") || "none"}. Emotion: ${values.leftEmotion}`;
    const rightScene = `Boy DINKLY and Girl DINKLY ${values.rightCharacterActions}. Setting: ${values.rightSetting}. Purposeful props: ${values.rightProps.join(", ") || "none"}. Emotion: ${values.rightEmotion}`;
    const allProps = [...new Set([...values.leftProps, ...values.rightProps])];
    try {
      const payload = {
        format: values.format,
        title_pair: { left: values.leftTitle, right: values.rightTitle },
        left_scene: leftScene,
        right_scene: rightScene,
        emotional_insight: values.emotionalInsight,
        emotional_theme: values.theme,
        category: values.category,
        left_character: values.leftCharacter,
        left_character_action: values.leftCharacterAction,
        left_setting: values.leftSetting,
        left_props: values.leftProps,
        left_emotion: values.leftEmotion,
        right_characters: "boy_and_girl",
        right_character_actions: values.rightCharacterActions,
        right_setting: values.rightSetting,
        right_props: values.rightProps,
        right_emotion: values.rightEmotion,
        shared_environment: values.sharedEnvironment,
        environmental_contrast: values.environmentalContrast,
        recommended_background_color: values.background,
        recommended_accent_color: values.accentColor,
        recommended_camera_angle: values.cameraAngle,
        brand_friendly: values.brandFriendly,
        potential_product_category: values.productCategory || null,
        brand_categories: values.productCategory ? [values.productCategory] : [],
        natural_product_placement: values.naturalProductPlacement || null,
        notes: values.notes || null,
        props: allProps,
        execution_risks: values.executionRisks,
        brand_placement_opportunities: values.naturalProductPlacement ? [values.naturalProductPlacement] : [],
        novel_angle: values.environmentalContrast,
        why_someone_would_share:
          developed?.whySomeoneWouldShare ?? "It reflects an ordinary relationship moment people recognize.",
        migration_version: 2,
      };
      const created = await api<{ concept: Concept }>("/api/concepts", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await api<{ score: Score }>(`/api/concepts/${created.concept.id}/score`, {
        method: "POST",
        body: JSON.stringify({ save: true }),
      });
      toast.success("Scene-rich concept saved—building its production prompt");
      router.push(`/prompt-builder?concept=${encodeURIComponent(created.concept.id)}&autogenerate=1`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save concept");
    }
  }

  const fieldError = (name: keyof ConceptFormValues) =>
    errors[name]?.message ? <p className="text-xs text-red-600">{String(errors[name]?.message)}</p> : null;

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Concept development"
        title={story ? `Develop ${story.title}` : "New story"}
        description="Design a complete minimalist scene, then continue directly into a prepopulated Nano Banana prompt."
        actions={<Button asChild variant="ghost"><Link href="/story-library"><ArrowLeft className="size-4" />Story library</Link></Button>}
      />

      {seedLoading && <div className="rounded-xl border border-line bg-white p-4 text-sm text-muted">Loading the selected Story Library data…</div>}
      {seedError && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{seedError}</div>}
      {story && <div className="rounded-xl border border-mustard/40 bg-mustard/10 p-4 text-sm"><strong>Seeded from Story Library:</strong> {story.title_direction || story.title} · {story.concept}</div>}

      <form onSubmit={handleSubmit(submit)} className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <div className="space-y-5">
          <Section title="Basic">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Format" error={fieldError("format")}><Select {...register("format")}>{promptFormats.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</Select></Field>
              <Field label="Category" error={fieldError("category")}><Input {...register("category")} /></Field>
              <Field label="Left title" error={fieldError("leftTitle")}><Input {...register("leftTitle")} /></Field>
              <Field label="Right title" error={fieldError("rightTitle")}><Input {...register("rightTitle")} /></Field>
              <Field label="Theme" error={fieldError("theme")}><Input {...register("theme")} /></Field>
              <Field label="Emotional insight" error={fieldError("emotionalInsight")}><Input {...register("emotionalInsight")} /></Field>
              <div className="sm:col-span-2 space-y-2">
                <Label>Who is alone in the left panel?</Label>
                <Controller name="leftCharacter" control={control} render={({ field }) => (
                  <div className="grid grid-cols-2 gap-3">
                    <CharacterChoice label="Boy DINKLY" detail="Exactly two hair tufts" value="boy" selected={field.value === "boy"} onChange={field.onChange} />
                    <CharacterChoice label="Girl DINKLY" detail="Red bow + connected ponytail" value="girl" selected={field.value === "girl"} onChange={field.onChange} />
                  </div>
                )} />
              </div>
            </div>
          </Section>

          <Section title="Left panel">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={`${leftCharacter === "girl" ? "Girl" : "Boy"} DINKLY action`} error={fieldError("leftCharacterAction")} className="sm:col-span-2"><Textarea {...register("leftCharacterAction")} /></Field>
              <Field label="Setting" error={fieldError("leftSetting")} className="sm:col-span-2"><Textarea {...register("leftSetting")} /></Field>
              <Field label="Props" error={fieldError("leftProps")} className="sm:col-span-2"><Controller name="leftProps" control={control} render={({ field }) => <TagInput value={field.value} onChange={field.onChange} />} /><Helper /></Field>
              <Field label="Emotion" error={fieldError("leftEmotion")} className="sm:col-span-2"><Textarea {...register("leftEmotion")} /></Field>
            </div>
          </Section>

          <Section title="Right panel">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2 rounded-xl border border-line bg-wash/50 p-3 text-sm"><strong>Characters:</strong> Boy DINKLY + Girl DINKLY together</div>
              <Field label="Character actions" error={fieldError("rightCharacterActions")} className="sm:col-span-2"><Textarea {...register("rightCharacterActions")} /></Field>
              <Field label="Setting" error={fieldError("rightSetting")} className="sm:col-span-2"><Textarea {...register("rightSetting")} /></Field>
              <Field label="Props" error={fieldError("rightProps")} className="sm:col-span-2"><Controller name="rightProps" control={control} render={({ field }) => <TagInput value={field.value} onChange={field.onChange} />} /><Helper /></Field>
              <Field label="Emotion" error={fieldError("rightEmotion")} className="sm:col-span-2"><Textarea {...register("rightEmotion")} /></Field>
            </div>
          </Section>

          <Section title="Visual system">
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Shared environment" error={fieldError("sharedEnvironment")} className="sm:col-span-3"><Textarea {...register("sharedEnvironment")} /></Field>
              <Field label="Environmental contrast" error={fieldError("environmentalContrast")} className="sm:col-span-3"><Textarea {...register("environmentalContrast")} /></Field>
              <Field label="Background" error={fieldError("background")}><Select {...register("background")}>{backgroundFamilies.map((color) => <option key={color}>{color}</option>)}</Select></Field>
              <Field label="Accent color" error={fieldError("accentColor")}><Select {...register("accentColor")}>{accentColors.map((color) => <option key={color}>{color}</option>)}</Select></Field>
              <Field label="Camera angle" error={fieldError("cameraAngle")}><Input {...register("cameraAngle")} /></Field>
            </div>
          </Section>

          <Section title="Brand">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="sm:col-span-2 flex items-center gap-3 rounded-xl border border-line p-3 text-sm"><input type="checkbox" {...register("brandFriendly")} className="size-4 accent-black" />This story can hold a natural brand prop</label>
              <Field label="Potential product category"><Input {...register("productCategory")} placeholder="Optional" /></Field>
              <Field label="Natural product placement"><Input {...register("naturalProductPlacement")} placeholder="Replace one prop the scene already needs" /></Field>
            </div>
          </Section>

          <Section title="Risk">
            <div className="space-y-4">
              <Field label="Execution risks" error={fieldError("executionRisks")}><Controller name="executionRisks" control={control} render={({ field }) => <TagInput value={field.value} onChange={field.onChange} placeholder="Add a known generation risk" />} /></Field>
              <Field label="Notes"><Textarea {...register("notes")} /></Field>
            </div>
          </Section>

          <Button type="submit" size="lg" disabled={isSubmitting || seedLoading || Boolean(seedError)}>
            {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            Save, score &amp; build prompt
          </Button>
        </div>

        <Card className="h-fit xl:sticky xl:top-24">
          <CardHeader><CardTitle>Story handoff</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start gap-3 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900"><CheckCircle2 className="mt-0.5 size-5 shrink-0" /><p>Character choice, actions, settings, panel-specific props, emotion, shared environment, contrast, colors, camera, and risks will travel into the prompt.</p></div>
            <div className="rounded-xl border border-line p-4 text-sm"><p><strong>Left:</strong> {leftCharacter === "girl" ? "Girl alone" : "Boy alone"}</p><p className="mt-1"><strong>Right:</strong> Boy + Girl together</p></div>
            <Summary label="Left props" values={leftProps} />
            <Summary label="Right props" values={rightProps} />
            <p className="text-xs leading-5 text-muted">A DINKLY scene should not be empty, but it should never be cluttered. Aim for one setting and two to five purposeful props per panel.</p>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent>{children}</CardContent></Card>;
}

function Field({ label, error, className, children }: { label: string; error?: React.ReactNode; className?: string; children: React.ReactNode }) {
  return <div className={`space-y-1.5 ${className ?? ""}`}><Label>{label}</Label>{children}{error}</div>;
}

function CharacterChoice({ label, detail, value, selected, onChange }: { label: string; detail: string; value: "boy" | "girl"; selected: boolean; onChange: (value: "boy" | "girl") => void }) {
  return <button type="button" aria-pressed={selected} onClick={() => onChange(value)} className={`rounded-xl border p-4 text-left transition ${selected ? "border-black bg-black text-white" : "border-line bg-white hover:bg-wash"}`}><span className="block text-sm font-semibold">{label}</span><span className={`mt-1 block text-xs ${selected ? "text-white/70" : "text-muted"}`}>{detail}</span></button>;
}

function TagInput({ value, onChange, placeholder = "Add a purposeful prop" }: { value: string[]; onChange: (value: string[]) => void; placeholder?: string }) {
  const [draft, setDraft] = useState("");
  function add() {
    const item = draft.trim().replace(/,$/, "");
    if (!item || value.includes(item)) return setDraft("");
    onChange([...value, item]);
    setDraft("");
  }
  return <div className="space-y-2"><div className="flex gap-2"><Input value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === ",") { event.preventDefault(); add(); } }} placeholder={placeholder} /><Button type="button" variant="outline" size="icon" aria-label="Add item" onClick={add}><Plus className="size-4" /></Button></div>{value.length > 0 && <div className="flex flex-wrap gap-2">{value.map((item) => <Badge key={item} className="gap-1.5">{item}<button type="button" aria-label={`Remove ${item}`} onClick={() => onChange(value.filter((valueItem) => valueItem !== item))}><X className="size-3" /></button></Badge>)}</div>}</div>;
}

function Helper() {
  return <p className="text-xs leading-5 text-muted">Use 2 to 5 purposeful props that help tell the story. Avoid decorative clutter.</p>;
}

function Summary({ label, values }: { label: string; values: string[] }) {
  return <div><p className="text-xs font-bold uppercase tracking-wide text-muted">{label}</p>{values.length ? <ul className="mt-2 space-y-1 text-xs leading-5 text-muted">{values.map((value) => <li key={value}>• {value}</li>)}</ul> : <p className="mt-2 text-xs text-muted">No props added yet.</p>}</div>;
}
