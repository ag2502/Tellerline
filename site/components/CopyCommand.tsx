"use client";

import { useState } from "react";

export function CopyCommand({ command, note }: { command: string; note?: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      setState("copied");
    } catch {
      setState("failed");
    }
    setTimeout(() => setState("idle"), 1800);
  };
  return (
    <div className="grid grid-cols-[2ch_1fr_auto] items-start gap-x-[1ch] py-1.5">
      <span className="dim" aria-hidden="true">
        $
      </span>
      <span className="min-w-0 break-words">
        <code>{command}</code>
        {note ? <span className="dim block text-[0.85em]">{note}</span> : null}
      </span>
      <button
        type="button"
        onClick={() => void copy()}
        className="dim cursor-pointer text-[0.85em] uppercase tracking-wide hover:text-p1"
        aria-label={`Copy: ${command}`}
      >
        <span aria-live="polite">{state === "copied" ? "copied" : state === "failed" ? "select it" : "copy"}</span>
      </button>
    </div>
  );
}
