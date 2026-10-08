"use client";

import { useEffect, useState } from "react";

import { clock } from "@/lib/timeline";

import { useCall } from "./CallContext";
import { PauseIcon, PlayIcon, ReplayIcon } from "./icons";

// Once the hero has scrolled away the call stays in reach: a small pill that plays and pauses it,
// says where it is, and can be pressed along its edge to skip about.
export function MiniPlayer() {
  const { call, now, playing, started, finished, toggle, seek } = useCall();
  const [away, setAway] = useState(false);

  useEffect(() => {
    const hero = document.getElementById("top");
    if (!hero) return;
    const observer = new IntersectionObserver(([entry]) => setAway(!entry.isIntersecting && entry.boundingClientRect.top < 0));
    observer.observe(hero);
    return () => observer.disconnect();
  }, []);

  const show = away;
  const label = playing ? "Pause the call" : finished ? "Play the call again" : started ? "Resume the call" : "Play the call";
  return (
    <div
      className={`fixed inset-x-0 bottom-0 z-40 flex justify-center px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] transition-[transform,opacity] duration-300 ease-out ${
        show ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-6 opacity-0"
      }`}
      aria-hidden={show ? undefined : true}
    >
      <div className="relative flex w-full max-w-[26rem] items-center gap-3 overflow-hidden rounded-full border border-white/15 bg-[#14112a]/95 py-2 pl-2 pr-5 shadow-[0_20px_60px_-12px_rgb(0_0_0/0.8)]">
        <button
          type="button"
          onClick={() => void toggle()}
          aria-label={label}
          tabIndex={show ? 0 : -1}
          className="grid h-11 w-11 shrink-0 [&_svg]:h-5 [&_svg]:w-5 cursor-pointer place-items-center rounded-full bg-ink text-board transition-transform hover:scale-105 active:scale-95"
        >
          {playing ? <PauseIcon /> : finished ? <ReplayIcon /> : <PlayIcon />}
        </button>
        <span className="min-w-0 flex-1 leading-tight">
          <span className="label block">now playing</span>
          <span className="block truncate text-[0.95rem] font-medium">{call.title}</span>
        </span>
        <span className="print shrink-0 text-[0.82rem] text-ink-2" aria-hidden="true">
          {clock(now)}
        </span>
        <input
          type="range"
          min={0}
          max={Math.round(call.duration_s * 10)}
          value={Math.round(now * 10)}
          tabIndex={show ? 0 : -1}
          onChange={(event) => seek(Number(event.target.value) / 10)}
          aria-label="Position in the call"
          className="absolute inset-x-5 bottom-0 h-1.5 cursor-pointer opacity-0"
        />
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 bottom-0 h-[3px] origin-left bg-[linear-gradient(95deg,#4fe3c8,#9d8cff,#ff6b8b)]"
          style={{ transform: `scaleX(${Math.min(1, now / call.duration_s)})` }}
        />
      </div>
    </div>
  );
}
