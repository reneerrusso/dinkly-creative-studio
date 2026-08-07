import { Skeleton } from "@/components/ui/skeleton";
export function LoadingState({ cards = 3 }: { cards?: number }) { return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="Loading"><span className="sr-only">Loading</span>{Array.from({ length: cards }).map((_, i) => <Skeleton key={i} className="h-40"/>)}</div>; }
