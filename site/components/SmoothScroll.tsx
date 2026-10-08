"use client";

import Lenis from "lenis";
import { useEffect } from "react";

// Inertial scrolling, the way the page's references move. Off under reduced motion, where the
// browser's own scroll is left alone.
export function SmoothScroll() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const lenis = new Lenis({ lerp: 0.2, anchors: { offset: -72 }, autoRaf: true });
    return () => lenis.destroy();
  }, []);
  return null;
}
