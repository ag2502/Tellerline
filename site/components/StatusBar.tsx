"use client";

import { useEffect, useState } from "react";

// A tmux status bar: the page's windows, the one in view marked with a star. Number keys jump
// between them, as tmux's prefix-number does.

export type StatusWindow = { id: string; name: string };

export function StatusBar({ windows }: { windows: StatusWindow[] }) {
  const [active, setActive] = useState(windows[0]?.id);

  useEffect(() => {
    const seen = new Map<string, number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) seen.set(entry.target.id, entry.intersectionRatio);
        let best: string | null = null;
        let most = 0;
        for (const item of windows) {
          const ratio = seen.get(item.id) ?? 0;
          if (ratio > most) {
            most = ratio;
            best = item.id;
          }
        }
        if (best) setActive(best);
      },
      { threshold: [0, 0.15, 0.3, 0.5, 0.75, 1], rootMargin: "-20% 0px -35% 0px" },
    );
    for (const item of windows) {
      const element = document.getElementById(item.id);
      if (element) observer.observe(element);
    }
    return () => observer.disconnect();
  }, [windows]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement;
      if (target.closest("input, textarea, [contenteditable=true]")) return;
      const number = Number(event.key);
      if (!Number.isInteger(number) || number < 0 || number >= windows.length) return;
      document.getElementById(windows[number].id)?.scrollIntoView({ block: "start" });
      history.replaceState(null, "", `#${windows[number].id}`);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [windows]);

  return (
    <nav
      aria-label="Sections"
      className="inverse fixed inset-x-0 bottom-0 z-30 flex h-[var(--status-h)] items-center gap-4 overflow-x-auto whitespace-nowrap px-[var(--gutter)] text-[0.9rem] [scrollbar-width:none]"
    >
      <span className="font-display tracking-wide">[tellerline]</span>
      <ol className="flex items-center gap-1">
        {windows.map((item, number) => {
          const current = item.id === active;
          return (
            <li key={item.id}>
              <a
                href={`#${item.id}`}
                aria-current={current ? "location" : undefined}
                aria-keyshortcuts={String(number)}
                className={`px-[0.7ch] py-1 no-underline ${
                  current ? "bg-tube text-p1" : "hover:bg-bloom"
                }`}
                style={current ? { textShadow: "var(--glow)" } : undefined}
              >
                {number}
                {/* On a phone only the window in view is named, as a narrow tmux does. */}
                <span className={current ? undefined : "hidden sm:inline"}>:{item.name}</span>
                {current ? "*" : ""}
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
