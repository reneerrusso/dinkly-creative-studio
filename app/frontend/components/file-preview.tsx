import Image from "next/image";
export function FilePreview({ url, name }: { url?: string; name?: string }) { if (!url) return null; return <div className="relative aspect-square overflow-hidden rounded-2xl border border-line bg-wash"><Image src={url} alt={name ?? "Uploaded comic"} fill unoptimized className="object-contain"/></div>; }
