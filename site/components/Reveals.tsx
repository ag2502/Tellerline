"use client";

import { useEffect } from "react";

// Bay titles and leads rise in as they arrive. Only what starts below the fold is hidden, and only
// once this has run, so nothing is ever lost without script.
export function Reveals() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const targets = [...document.querySelectorAll<HTMLElement>("[data-reveal-target]")].filter(
      (element) => element.getBoundingClientRect().top > window.innerHeight * 0.92,
    );
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          (entry.target as HTMLElement).dataset.in = "";
          observer.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -12% 0px" },
    );
    for (const element of targets) {
      element.dataset.reveal = "";
      observer.observe(element);
    }
    return () => observer.disconnect();
  }, []);
  return null;
}
