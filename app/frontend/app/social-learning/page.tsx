"use client";

import Link from "next/link";
import { BarChart3, BrainCircuit, Download, FileQuestion, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { LearningCard } from "@/components/learning-card";
import { LoadingState } from "@/components/loading-state";
import { PageHeader } from "@/components/page-header";
import { SocialPostTable } from "@/components/social-post-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, getLearnings, getPatterns, getSocialPosts } from "@/lib/api";
import type { Learning, PatternData, SocialPost } from "@/lib/types";

interface Report { name: string; path: string; created_at: string; content: string }

export default function SocialLearningPage() {
  const [posts, setPosts] = useState<SocialPost[]>();
  const [learnings, setLearnings] = useState<Learning[]>([]);
  const [patterns, setPatterns] = useState<PatternData>();
  const [reports, setReports] = useState<Report[]>([]);
  const [confidence, setConfidence] = useState("all");
  const [reportIndex, setReportIndex] = useState(0);
  const report = reports[reportIndex];
  const filteredLearnings = useMemo(() => confidence === "all" ? learnings : learnings.filter(item => item.confidence === confidence), [learnings, confidence]);
  const load = useCallback(() => Promise.all([getSocialPosts(), getLearnings(), getPatterns(), api<Report[]>("/api/social-reports")]).then(([postData, learningData, patternData, reportData]) => { setPosts(postData); setLearnings(learningData); setPatterns(patternData); setReports(reportData); }), []);
  useEffect(() => { load().catch(() => setPosts([])); }, [load]);

  async function analyze() {
    try { await api<{ generated: string }>("/api/social-learning/analyze", { method: "POST", body: "{}" }); await load(); setReportIndex(0); toast.success("Social learning updated"); }
    catch (error) { toast.error(error instanceof Error ? error.message : "Analysis failed"); }
  }
  function downloadReport() { if (!report) return; const url = URL.createObjectURL(new Blob([report.content], { type: "text/markdown" })); const link = document.createElement("a"); link.href = url; link.download = report.name; link.click(); URL.revokeObjectURL(url); }

  return <div className="space-y-7"><PageHeader eyebrow="Learn" title="Social learning" description="Facts, observed traits, hypotheses, and open questions stay visibly separate. Every pattern carries its sample size." actions={<><Button variant="outline" onClick={analyze}><RefreshCw className="size-4"/>Run analysis</Button><Button asChild><Link href="/social-learning/ingest"><Plus className="size-4"/>Ingest post</Link></Button></>}/>{!posts ? <LoadingState cards={4}/> : <Tabs defaultValue="posts"><TabsList><TabsTrigger value="posts">Posts</TabsTrigger><TabsTrigger value="patterns">Patterns</TabsTrigger><TabsTrigger value="learnings">Learnings</TabsTrigger><TabsTrigger value="report">Reports</TabsTrigger></TabsList><TabsContent value="posts"><Card>{posts.length ? <CardContent className="p-0"><SocialPostTable posts={posts}/></CardContent> : <CardContent className="p-5"><EmptyState icon={BarChart3} title="No social records yet" description="Add your strongest comics to begin building evidence-backed creative learnings." action={<Button asChild size="sm"><Link href="/social-learning/ingest">Ingest first post</Link></Button>}/></CardContent>}</Card></TabsContent><TabsContent value="patterns">{patterns && <div className="grid gap-4 lg:grid-cols-3"><PatternCard title="Themes" items={patterns.themes} sample={patterns.sample_size}/><PatternCard title="Formats" items={patterns.formats} sample={patterns.sample_size}/><PatternCard title="Backgrounds" items={patterns.backgrounds} sample={patterns.sample_size}/><Card className="lg:col-span-3"><CardContent className="p-5 text-sm leading-6 text-muted"><strong className="text-ink">Interpretation boundary:</strong> {patterns.causation_warning}</CardContent></Card></div>}</TabsContent><TabsContent value="learnings"><div className="mb-4 flex justify-end"><Select aria-label="Confidence filter" value={confidence} onChange={event => setConfidence(event.target.value)} className="w-48"><option value="all">All confidence levels</option><option value="high">High confidence</option><option value="medium">Medium confidence</option><option value="low">Low confidence</option></Select></div>{filteredLearnings.length ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{filteredLearnings.map(learning => <LearningCard key={learning.learning_id} learning={learning}/>)}</div> : <EmptyState icon={BrainCircuit} title="No learnings match" description="One post can establish facts and traits, but not a broad performance law."/>}</TabsContent><TabsContent value="report"><Card><CardHeader className="flex-row items-center justify-between gap-4"><div><CardTitle>Analysis reports</CardTitle><p className="mt-1 text-xs text-muted">{report ? `${report.name} · ${new Date(report.created_at).toLocaleString()}` : "No saved reports"}</p></div>{report && <div className="flex gap-2"><Select aria-label="Compare report" value={reportIndex} onChange={event => setReportIndex(Number(event.target.value))} className="w-48">{reports.map((item, index) => <option key={item.path} value={index}>{index === 0 ? "Latest" : `Previous ${index}`} · {item.name}</option>)}</Select><Button variant="outline" size="icon" aria-label="Download report" onClick={downloadReport}><Download className="size-4"/></Button></div>}</CardHeader><CardContent>{report ? <pre className="whitespace-pre-wrap font-sans text-sm leading-7">{report.content}</pre> : <EmptyState icon={FileQuestion} title="No generated report" description="Run analysis after ingesting at least one post."/>}</CardContent></Card></TabsContent></Tabs>}</div>;
}

function PatternCard({ title, items, sample }: { title: string; items: { value: string; count: number }[]; sample: number }) { return <Card><CardHeader><CardTitle>{title}</CardTitle><p className="text-xs text-muted">Sample: {sample} post{sample === 1 ? "" : "s"}</p></CardHeader><CardContent className="space-y-3">{items.length ? items.slice(0, 6).map(item => <div key={item.value} className="flex items-center justify-between text-sm"><span className="capitalize">{item.value}</span><strong>{item.count}</strong></div>) : <p className="text-sm text-muted">Not enough recorded traits.</p>}</CardContent></Card>; }
