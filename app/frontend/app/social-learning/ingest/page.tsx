"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, Check, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { ImageDropzone } from "@/components/image-dropzone";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { socialPostSchema, type SocialPostFormInput, type SocialPostFormValues } from "@/lib/schemas";

const defaults: SocialPostFormValues = { title: "", platform: null, postDate: null, views: null, shares: null, likes: null, comments: null, saves: null, format: "x-with-you", storyline: null, emotionalTheme: null, leftPanelSummary: null, rightPanelSummary: null, backgroundColor: null, accentColor: null, cameraAngle: null, props: null, brandIntegration: null, uploadedAssetReference: null, uploadedAssetHash: null, notes: null };
const stepNames = ["Image", "Metadata", "Metrics", "Creative traits", "Review & save"];

export default function IngestPage() {
  const [step, setStep] = useState(1);
  const [saved, setSaved] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting }, watch } = useForm<SocialPostFormInput, unknown, SocialPostFormValues>({ resolver: zodResolver(socialPostSchema), defaultValues: defaults });
  const values = watch();
  const metricValues = [values.views, values.shares, values.likes, values.comments, values.saves];
  const known = metricValues.filter(value => value !== null && value !== undefined).length;

  async function submit(formValues: SocialPostFormValues) {
    try {
      let asset: { path: string; sha256: string } | null = null;
      if (file) { const form = new FormData(); form.append("file", file); asset = await api("/api/social-posts/upload", { method: "POST", body: form }); }
      const payload = { title: formValues.title, platform: formValues.platform || null, post_date: formValues.postDate || null, views: formValues.views, shares: formValues.shares, likes: formValues.likes, comments: formValues.comments, saves: formValues.saves, format: formValues.format || null, storyline: formValues.storyline || null, emotional_theme: formValues.emotionalTheme || null, left_panel_summary: formValues.leftPanelSummary || null, right_panel_summary: formValues.rightPanelSummary || null, background_color: formValues.backgroundColor || null, accent_color: formValues.accentColor || null, camera_angle: formValues.cameraAngle || null, props: split(formValues.props), brand_integration: formValues.brandIntegration || null, uploaded_asset_reference: asset?.path ?? null, uploaded_asset_hash: asset?.sha256 ?? null, notes: formValues.notes || null };
      await api("/api/social-posts", { method: "POST", body: JSON.stringify(payload) }); setSaved(true); toast.success("Social post recorded without guessed metrics");
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not ingest post"); }
  }

  return <div className="space-y-7"><PageHeader eyebrow="Evidence intake" title="Ingest a social post" description="Record the post as published. Leave unavailable metrics blank—the system treats missing as unknown, never zero." actions={<Button asChild variant="ghost"><Link href="/social-learning"><ArrowLeft className="size-4"/>Social learning</Link></Button>}/><div className="mx-auto max-w-4xl"><div className="mb-5 grid grid-cols-5 gap-2">{stepNames.map((name, index) => <div key={name} className={`border-t-2 pt-2 text-[11px] font-semibold ${step >= index + 1 ? "border-ink text-ink" : "border-line text-muted"}`}>0{index + 1} · <span className="hidden sm:inline">{name}</span></div>)}</div><form onSubmit={handleSubmit(submit)}><Card><CardContent className="p-6">{step === 1 && <Step><ImageDropzone onFile={setFile}/><p className="text-xs leading-5 text-muted">An image is recommended for visual learning but not required. Its hash participates in duplicate protection.</p><Next onClick={() => setStep(2)}/></Step>}{step === 2 && <Step><Field label="Working title" error={errors.title?.message}><Input {...register("title")} placeholder="Sunday Morning carousel"/></Field><div className="grid gap-4 sm:grid-cols-2"><Field label="Platform"><Input {...register("platform")} placeholder="Instagram"/></Field><Field label="Posting date"><Input type="date" {...register("postDate")}/></Field></div><Field label="Storyline or carousel theme"><Input {...register("storyline")} placeholder="Sundays, Target run, a win, snacks…"/></Field><Nav back={() => setStep(1)} next={() => setStep(3)}/></Step>}{step === 3 && <Step><div className="rounded-xl bg-mustard/15 p-4 text-sm"><strong>{known} of 5 core metrics supplied.</strong> Missing fields display as Missing and are excluded from rates.</div><div data-testid="missing-metrics" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{(["views", "shares", "likes", "comments", "saves"] as const).map(name => <Field key={name} label={name[0].toUpperCase() + name.slice(1)}><Input type="number" min="0" {...register(name)} placeholder="Leave blank if unknown"/></Field>)}</div><Nav back={() => setStep(2)} next={() => setStep(4)}/></Step>}{step === 4 && <Step><div className="grid gap-4 sm:grid-cols-2"><Field label="Format"><Input {...register("format")} placeholder="x-with-you"/></Field><Field label="Emotional theme"><Input {...register("emotionalTheme")} placeholder="companionship"/></Field><Field label="Left panel summary"><Textarea {...register("leftPanelSummary")}/></Field><Field label="Right panel summary"><Textarea {...register("rightPanelSummary")}/></Field><Field label="Background color"><Input {...register("backgroundColor")}/></Field><Field label="Accent color"><Input {...register("accentColor")}/></Field><Field label="Camera angle"><Input {...register("cameraAngle")}/></Field><Field label="Props, comma separated"><Input {...register("props")}/></Field></div><Field label="Brand integration"><Input {...register("brandIntegration")} placeholder="Leave blank when unbranded"/></Field><Field label="Observed notes"><Textarea {...register("notes")} placeholder="Song, carousel order, exact observed traits. Keep hypotheses out of this field."/></Field><Nav back={() => setStep(3)} next={() => setStep(5)}/></Step>}{step === 5 && (saved ? <div className="py-10 text-center"><div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700"><Check className="size-6"/></div><h2 className="mt-4 text-xl font-semibold">Post recorded</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">The asset is local, missing data stayed missing, and duplicate protection is active.</p><div className="mt-5 flex justify-center gap-2"><Button asChild variant="outline"><Link href="/social-learning">View post evidence</Link></Button><Button asChild><Link href="/social-learning">Analyze now</Link></Button></div></div> : <Step><div className="grid gap-3 rounded-xl bg-wash p-4 sm:grid-cols-2"><Review label="Title" value={values.title || "Missing — required"}/><Review label="Post" value={[values.platform, values.postDate].filter(Boolean).join(" · ") || "Metadata missing"}/><Review label="Metrics" value={`${known} of 5 core metrics recorded`}/><Review label="Creative classification" value={[values.format, values.emotionalTheme, values.backgroundColor].filter(Boolean).join(" · ") || "Traits missing"}/><Review label="Asset" value={file?.name ?? "No image supplied"}/><Review label="Duplicate fingerprint" value="Platform + date + title + image hash when present"/></div><p className="text-xs leading-5 text-muted">Review the record as fact. The studio does not infer or fill missing values during ingestion.</p><div className="flex gap-2"><Button type="button" variant="outline" onClick={() => setStep(4)}>Back</Button><Button type="submit" disabled={isSubmitting}>{isSubmitting ? <Loader2 className="size-4 animate-spin"/> : <Check className="size-4"/>}Review and save</Button></div></Step>)}</CardContent></Card></form></div></div>;
}

function Step({ children }: { children: React.ReactNode }) { return <div className="space-y-5">{children}</div>; }
function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) { const optionalMetric = ["Views", "Shares", "Likes", "Comments", "Saves"].includes(label); return <div className="space-y-1.5"><Label>{label}</Label>{children}{optionalMetric && <p className="text-[10px] text-muted">Leave blank if unknown</p>}{error && <p className="text-xs text-red-600">{error}</p>}</div>; }
function Next({ onClick }: { onClick: () => void }) { return <Button type="button" onClick={onClick}>Continue <ArrowRight className="size-4"/></Button>; }
function Nav({ back, next }: { back: () => void; next: () => void }) { return <div className="flex gap-2"><Button type="button" variant="outline" onClick={back}>Back</Button><Next onClick={next}/></div>; }
function Review({ label, value }: { label: string; value: string }) { return <div><p className="text-[10px] font-bold uppercase tracking-wide text-muted">{label}</p><p className="mt-1 text-sm">{value}</p></div>; }
function split(value?: string | null) { const items = (value ?? "").split(",").map(item => item.trim()).filter(Boolean); return items.length ? items : null; }
