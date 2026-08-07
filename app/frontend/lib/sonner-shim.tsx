"use client";

import { useEffect, useState } from "react";

type ToastKind = "success" | "error" | "info";
type ToastDetail = { id: number; kind: ToastKind; message: string };

const EVENT_NAME = "dinkly:toast";

function publish(kind: ToastKind, message: string) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<ToastDetail>(EVENT_NAME, {
      detail: { id: Date.now(), kind, message },
    }),
  );
}

export const toast = {
  success: (message: string) => publish("success", message),
  error: (message: string) => publish("error", message),
  info: (message: string) => publish("info", message),
};

export function Toaster({ position: _position, richColors: _richColors }: { position?: string; richColors?: boolean }) {
  const [items, setItems] = useState<ToastDetail[]>([]);

  useEffect(() => {
    function show(event: Event) {
      const detail = (event as CustomEvent<ToastDetail>).detail;
      setItems((current) => [...current, detail]);
      window.setTimeout(
        () => setItems((current) => current.filter((item) => item.id !== detail.id)),
        3200,
      );
    }
    window.addEventListener(EVENT_NAME, show);
    return () => window.removeEventListener(EVENT_NAME, show);
  }, []);

  return (
    <div aria-live="polite" className="fixed bottom-4 right-4 z-[100] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          role={item.kind === "error" ? "alert" : "status"}
          className={`rounded-xl border px-4 py-3 text-sm font-semibold shadow-lg ${
            item.kind === "error"
              ? "border-red-200 bg-red-50 text-red-800"
              : item.kind === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                : "border-blue-200 bg-blue-50 text-blue-900"
          }`}
        >
          {item.message}
        </div>
      ))}
    </div>
  );
}
