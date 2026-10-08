"use client";

import { useEffect, useRef } from "react";

import type { Span } from "@/lib/timeline";

// The whole call as a printed trace: the caller above the line in amber, Tellerline below it in
// blue, inked in as the call plays. The waits between a caller finishing and Tellerline answering
// are bracketed underneath, since they are what this project measures.

const BAR = 2;
const PITCH = 3;
const COLOURS = {
  idle: "#c3cad2",
  caller: "#d9a21f",
  agent: "#2f6fd6",
  axis: "#9aa3ad",
  head: "#16191d",
  gap: "#16191d",
  band: "rgba(242, 193, 78, 0.22)",
};

type Props = {
  caller: number[];
  agent: number[];
  hz: number;
  duration: number;
  gaps: Span[];
  now: React.RefObject<number>;
  playing: boolean;
  highlight: Span | null;
  onSeek: (seconds: number) => void;
  label: string;
};

export function Waveform({ caller, agent, hz, duration, gaps, now, playing, highlight, onSeek, label }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const context = element.getContext("2d");
    if (!context) return;
    let frame = 0;
    let lastDrawn = -1;
    let width = 0;
    let height = 0;

    const level = (values: number[], from: number, to: number) => {
      let peak = 0;
      const start = Math.floor(from * hz);
      const end = Math.max(start + 1, Math.ceil(to * hz));
      for (let i = start; i < end && i < values.length; i++) peak = Math.max(peak, values[i]);
      return peak / 255;
    };

    const draw = () => {
      const ratio = window.devicePixelRatio || 1;
      const rect = element.getBoundingClientRect();
      if (rect.width !== width || rect.height !== height) {
        width = rect.width;
        height = rect.height;
        element.width = Math.round(width * ratio);
        element.height = Math.round(height * ratio);
      }
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);

      const trace = height - 12; // room underneath for the wait brackets
      const middle = Math.round(trace / 2);
      const reach = middle - 2;
      if (highlight) {
        const x1 = (highlight[0] / duration) * width;
        const x2 = (highlight[1] / duration) * width;
        context.fillStyle = COLOURS.band;
        context.fillRect(x1, 0, Math.max(2, x2 - x1), trace);
      }

      const columns = Math.floor(width / PITCH);
      const played = (now.current ?? 0) / duration;
      for (let column = 0; column < columns; column++) {
        const from = (column / columns) * duration;
        const to = ((column + 1) / columns) * duration;
        const isPlayed = column / columns <= played;
        const x = column * PITCH;
        const up = Math.max(0, Math.round(level(caller, from, to) * reach));
        if (up) {
          context.fillStyle = isPlayed ? COLOURS.caller : COLOURS.idle;
          context.fillRect(x, middle - up, BAR, up);
        }
        const down = Math.max(0, Math.round(level(agent, from, to) * reach));
        if (down) {
          context.fillStyle = isPlayed ? COLOURS.agent : COLOURS.idle;
          context.fillRect(x, middle + 1, BAR, down);
        }
      }
      // The axis, then each reply wait as a bracket under the trace.
      context.fillStyle = COLOURS.axis;
      for (let x = 0; x < width; x += 6) context.fillRect(x, middle, 3, 1);
      context.fillStyle = COLOURS.gap;
      for (const [start, end] of gaps) {
        const x1 = (start / duration) * width;
        const x2 = Math.max(x1 + 2, (end / duration) * width);
        context.fillRect(x1, height - 3, x2 - x1, 1.5);
        context.fillRect(x1, height - 8, 1.5, 6);
        context.fillRect(x2 - 1.5, height - 8, 1.5, 6);
      }
      const head = Math.min(width - 2, Math.max(0, played * width));
      context.fillStyle = COLOURS.head;
      context.fillRect(head, 0, 2, trace);
      context.beginPath();
      context.moveTo(head - 4, 0);
      context.lineTo(head + 6, 0);
      context.lineTo(head + 1, 6);
      context.closePath();
      context.fill();
      lastDrawn = now.current ?? 0;
    };

    const loop = () => {
      if ((now.current ?? 0) !== lastDrawn) draw();
      frame = requestAnimationFrame(loop);
    };
    draw();
    if (playing) frame = requestAnimationFrame(loop);
    const observer = new ResizeObserver(draw);
    observer.observe(element);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [caller, agent, hz, duration, gaps, now, playing, highlight]);

  const seek = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    onSeek(Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)) * duration);
  };

  const step = (event: React.KeyboardEvent<HTMLCanvasElement>) => {
    const position = now.current ?? 0;
    if (event.key === "ArrowRight") onSeek(Math.min(duration, position + 5));
    else if (event.key === "ArrowLeft") onSeek(Math.max(0, position - 5));
    else if (event.key === "Home") onSeek(0);
    else return;
    event.preventDefault();
  };

  return (
    <canvas
      ref={canvas}
      role="slider"
      tabIndex={0}
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={Math.round(duration)}
      aria-valuenow={Math.round(now.current ?? 0)}
      aria-valuetext={`${Math.round(now.current ?? 0)} of ${Math.round(duration)} seconds`}
      onPointerDown={seek}
      onKeyDown={step}
      className="block h-[4.25rem] w-full cursor-pointer touch-none rounded-[2px]"
    />
  );
}
