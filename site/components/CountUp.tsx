"use client";

import { useEffect, useRef } from "react";

// A figure that counts up to itself once, as it scrolls into view. The real value is in the
// markup, so without script, or under reduced motion, it simply reads as it is.
export function CountUp({ value, className }: { value: string; className?: string }) {
  const element = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const target = element.current;
    const match = value.match(/^(\d+(?:\.\d+)?)(.*)$/);
    if (!target || !match || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const end = Number(match[1]);
    const places = match[1].split(".")[1]?.length ?? 0;
    let frame = 0;
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      observer.disconnect();
      const start = performance.now();
      const tick = (now: number) => {
        const share = Math.min(1, (now - start) / 1100);
        const eased = 1 - Math.pow(1 - share, 3);
        target.textContent = (end * eased).toFixed(places) + match[2];
        if (share < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    });
    observer.observe(target);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [value]);
  return (
    <span ref={element} className={className}>
      {value}
    </span>
  );
}
