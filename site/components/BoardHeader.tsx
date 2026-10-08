"use client";

import { useEffect, useState } from "react";

import { GitHubIcon } from "./icons";
import { REPO } from "./links";
import { StripMark } from "./StripMark";

// The head of the strip board: the bays it holds, the one in view marked. Number keys jump
// between bays.

export type Bay = { id: string; name: string };

export function BoardHeader({ bays }: { bays: Bay[] }) {
  const [active, setActive] = useState(bays[0]?.id);

  useEffect(() => {
    const seen = new Map<string, number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) seen.set(entry.target.id, entry.intersectionRatio);
        let best: string | null = null;
        let most = 0;
        for (const item of bays) {
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
    for (const item of bays) {
      const element = document.getElementById(item.id);
      if (element) observer.observe(element);
    }
    return () => observer.disconnect();
  }, [bays]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement;
      if (target.closest("input, textarea, [contenteditable=true]")) return;
      const number = Number(event.key);
      if (!Number.isInteger(number) || number < 0 || number >= bays.length) return;
      document.getElementById(bays[number].id)?.scrollIntoView({ block: "start" });
      history.replaceState(null, "", `#${bays[number].id}`);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [bays]);

  return (
    <header className="sticky top-0 z-40 border-b border-rail bg-board shadow-[0_1px_0_rgb(255_255_255/0.6)]">
      <div className="mx-auto flex h-[var(--header-h)] max-w-[90rem] items-center gap-3 px-[var(--gutter)] sm:gap-6">
        <a href="#top" className="flex shrink-0 items-center gap-2.5 no-underline" aria-label="Tellerline, to the top">
          <StripMark className="h-[18px] w-[34px]" />
          <span className="callsign text-[1.35rem] tracking-[0.01em]">Tellerline</span>
        </a>
        <nav aria-label="Bays" className="min-w-0 flex-1 overflow-x-auto [mask-image:linear-gradient(90deg,#000_80%,transparent)] [scrollbar-width:none] md:[mask-image:none]">
          <ol className="flex w-max items-center gap-1">
            {bays.map((item, number) => {
              const current = item.id === active;
              return (
                <li key={item.id}>
                  <a
                    href={`#${item.id}`}
                    aria-current={current ? "location" : undefined}
                    aria-keyshortcuts={String(number)}
                    className={`flex items-center gap-1.5 rounded-[5px] px-2 py-1.5 text-[0.8rem] font-semibold uppercase tracking-[0.07em] no-underline transition-colors duration-150 ${
                      current ? "bg-ink text-strip" : "text-ink-2 hover:bg-well hover:text-ink"
                    }`}
                  >
                    <span className={`print hidden text-[0.72rem] md:inline ${current ? "text-amber" : "text-ink-3"}`}>{number}</span>
                    <span>{item.name}</span>
                  </a>
                </li>
              );
            })}
          </ol>
        </nav>
        <a className="key min-h-[2.4rem] shrink-0 px-3 py-0 text-[0.85rem] sm:px-3.5" data-primary="" href={REPO}>
          <GitHubIcon />
          <span className="hidden sm:inline">GitHub</span>
        </a>
      </div>
    </header>
  );
}
