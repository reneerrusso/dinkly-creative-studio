"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

export function DinklyAgentAvatar({ source, className }: { source?: string; className?: string }) {
  const fallback = "/agents/social-intelligence.png";
  const [image, setImage] = useState(source || fallback);
  useEffect(() => setImage(source || fallback), [source]);
  return <span className={cn("relative block size-10 shrink-0 overflow-hidden rounded-xl border border-black/[0.07] bg-[#ead8ae]", className)}>
    <Image src={image} alt="DINKLY Agent" fill unoptimized sizes="40px" onError={() => setImage(fallback)} className="scale-[1.65] object-cover object-[50%_34%]"/>
  </span>;
}
