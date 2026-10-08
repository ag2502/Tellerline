"use client";

import { Fragment, useState } from "react";

import { CheckIcon, CopyIcon } from "./icons";

// A command breaks only between its words: a flag broken at its hyphen ("--port- forwarder")
// reads as two words. A word too long for a phone's line can still break.
const LONGEST_UNBROKEN = 24;

function Words({ command }: { command: string }) {
  return command.split(" ").map((word, index) => (
    <Fragment key={index}>
      {index ? " " : null}
      <span className={word.length <= LONGEST_UNBROKEN ? "whitespace-nowrap" : undefined}>{word}</span>
    </Fragment>
  ));
}

// One command as a strip: its step, the command and what it does, and a key that copies it.
export function CopyCommand({ step, command, note }: { step: number; command: string; note?: string }) {
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
    <div className="holder-plain">
      <div className="strip grid grid-cols-[2.25rem_minmax(0,1fr)_auto] items-stretch">
        <span className="box print flex items-start justify-center px-0 pt-[0.55rem] text-[0.8rem] font-semibold text-ink-3">
          {step}
        </span>
        <span className="box min-w-0 break-words">
          <code className="text-[0.85rem] font-medium leading-relaxed">
            <Words command={command} />
          </code>
          {note ? <span className="block text-[0.8rem] leading-snug text-ink-2">{note}</span> : null}
        </span>
        <span className="box flex items-center px-1.5">
          <button
            type="button"
            onClick={() => void copy()}
            className={`flex min-h-[2.5rem] min-w-[2.5rem] cursor-pointer items-center justify-center gap-1.5 rounded-[4px] px-2 text-[0.75rem] font-semibold uppercase tracking-[0.08em] transition-colors duration-150 hover:bg-well ${
              state === "copied" ? "text-blue-ink" : "text-ink-2 hover:text-ink"
            }`}
            aria-label={`Copy: ${command}`}
          >
            {state === "copied" ? <CheckIcon className="h-4 w-4" /> : <CopyIcon className="h-4 w-4" />}
            <span aria-live="polite" className="hidden sm:inline">
              {state === "copied" ? "copied" : state === "failed" ? "select it" : "copy"}
            </span>
          </button>
        </span>
      </div>
    </div>
  );
}
