import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";
import { AppSidebar } from "@/components/app-sidebar";
import { DinklyAgentBar } from "@/components/dinkly-agent-bar";
import { TopBar } from "@/components/top-bar";

export const metadata: Metadata = { metadataBase: new URL("http://127.0.0.1:3000"), title: { default: "DINKLY Generation Engine", template: "%s · DINKLY Generation Engine" }, description: "Original IP. Scalable content. Human taste.", robots: { index: false, follow: false }, openGraph: { title: "DINKLY Generation Engine", description: "A character-locked DINKLY production system from story brief to human approval.", images: [{ url: "/social-preview.png", width: 1536, height: 1024, alt: "DINKLY Generation Engine" }] } };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body><div className="flex min-h-screen"><AppSidebar/><div className="min-w-0 flex-1"><TopBar/><DinklyAgentBar/><main className="mx-auto w-full max-w-[1500px] p-4 sm:p-6 lg:p-8">{children}</main></div></div><Toaster position="bottom-right" richColors/></body></html>; }
