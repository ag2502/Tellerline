"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { stage } from "@/lib/stage";

import type { Formation } from "./formations";

// The 3D scene loads after the page, only where WebGL works; without it the page is complete,
// and the bays' 2D figures carry every number.
const Scene = dynamic(() => import("./Scene"), { ssr: false });

function webgl(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

export function Stage({ data }: { data: Formation["data"] }) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const ok = webgl();
    setReady(ok);
    if (ok) document.documentElement.dataset.stage = "on";
    const onMove = (event: PointerEvent) => {
      stage.pointer.x = (event.clientX / window.innerWidth) * 2 - 1;
      stage.pointer.y = (event.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, []);
  if (!ready) return null;
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-0">
      <Scene data={data} />
    </div>
  );
}
