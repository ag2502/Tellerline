"use client";

import { useEffect, useRef } from "react";

// A band of the page's measured claims running across the board, faster while the page scrolls.
export function Marquee({ items }: { items: string[] }) {
  const track = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = track.current;
    if (!element || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let offset = 0;
    let lastY = window.scrollY;
    let speed = 0;
    let frame = 0;
    let last = performance.now();
    let visible = true;
    const loop = (time: number) => {
      if (!visible) {
        frame = 0;
        return;
      }
      const delta = Math.min(0.05, (time - last) / 1000);
      last = time;
      const y = window.scrollY;
      speed += (Math.abs(y - lastY) * 6 - speed) * 0.1;
      lastY = y;
      offset -= (60 + speed) * delta;
      const half = element.scrollWidth / 2;
      if (-offset > half) offset += half;
      element.style.transform = `translate3d(${offset}px, 0, 0)`;
      frame = requestAnimationFrame(loop);
    };
    // Off screen it stops; back on screen it picks up where it was.
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible && !frame) {
        last = performance.now();
        frame = requestAnimationFrame(loop);
      }
    });
    observer.observe(element);
    frame = requestAnimationFrame(loop);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, []);
  const line = items.join("  ·  ") + "  ·  ";
  return (
    <div className="relative z-10 overflow-hidden bg-ink py-3 text-strip" aria-hidden="true">
      <div ref={track} className="callsign flex w-max whitespace-nowrap text-[clamp(1.6rem,1rem+2.4vw,3.2rem)] will-change-transform">
        <span className="pr-[0.5em]">{line}</span>
        <span className="pr-[0.5em]">{line}</span>
      </div>
    </div>
  );
}
