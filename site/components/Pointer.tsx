"use client";

import { useEffect, useRef } from "react";

// A ring that trails the pointer and opens over anything that can be pressed; keys lean toward
// it. Only with a fine pointer and motion allowed; the system cursor always stays.
export function Pointer() {
  const ring = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = ring.current;
    if (!element) return;
    if (!window.matchMedia("(pointer: fine)").matches || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let x = -100;
    let y = -100;
    let rx = x;
    let ry = y;
    let open = 0;
    let target = 0;
    let frame = 0;
    let key: HTMLElement | null = null;
    const onMove = (event: PointerEvent) => {
      if (!frame) frame = requestAnimationFrame(loop);
      x = event.clientX;
      y = event.clientY;
      const hit = (event.target as HTMLElement).closest<HTMLElement>("a, button, summary, [role=slider], [data-stage-slot=hero], input");
      target = hit ? 1 : 0;
      const next = (event.target as HTMLElement).closest<HTMLElement>(".key");
      if (key && key !== next) key.style.translate = "";
      key = next;
      if (key) {
        const box = key.getBoundingClientRect();
        key.style.translate = `${(x - (box.left + box.width / 2)) * 0.12}px ${(y - (box.top + box.height / 2)) * 0.18}px`;
      }
    };
    const loop = () => {
      rx += (x - rx) * 0.22;
      ry += (y - ry) * 0.22;
      open += (target - open) * 0.18;
      const size = 22 + open * 30;
      element.style.transform = `translate3d(${rx - size / 2}px, ${ry - size / 2}px, 0)`;
      element.style.width = element.style.height = `${size}px`;
      element.style.opacity = String(0.35 + open * 0.5);
      // At rest the loop stops; the next pointer move starts it again.
      const settled = Math.abs(x - rx) < 0.3 && Math.abs(y - ry) < 0.3 && Math.abs(target - open) < 0.01;
      frame = settled ? 0 : requestAnimationFrame(loop);
    };
    element.style.display = "block";
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(frame);
    };
  }, []);
  return (
    <div
      ref={ring}
      aria-hidden="true"
      className="pointer-events-none fixed left-0 top-0 z-50 hidden rounded-full border-[1.5px] border-ink"
    />
  );
}
