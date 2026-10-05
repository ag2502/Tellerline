"use client";

import { useEffect, useRef } from "react";

import type { Span } from "@/lib/timeline";

// The whole call as a dot-matrix strip: the caller above the line, Tellerline below it. The
// part already played glows; the gaps between a caller finishing and Tellerline answering are
// marked underneath, since they are what this project measures.

const DOT = 2;
const PITCH = 3;
const COLOURS = {
  idle: "#176e3a",
  caller: "#23a14b",
  agent: "#33ff66",
  head: "#b6ffb6",
  gap: "#b6ffb6",
};

type Props = {
  caller: number[];
  agent: number[];
  hz: number;
  duration: number;
  gaps: Span[];
  now: React.RefObject<number>;
  playing: boolean;
  onSeek: (seconds: number) => void;
  label: string;
};

export function Waveform({ caller, agent, hz, duration, gaps, now, playing, onSeek, label }: Props) {
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

      const columns = Math.floor(width / PITCH);
      const lane = Math.floor((height - 10) / 2 / PITCH); // dots per half, leaving room for gap marks
      const middle = lane * PITCH;
      const played = (now.current ?? 0) / duration;
      for (let column = 0; column < columns; column++) {
        const from = (column / columns) * duration;
        const to = ((column + 1) / columns) * duration;
        const isPlayed = column / columns <= played;
        const x = column * PITCH;
        const up = Math.round(level(caller, from, to) * lane);
        context.fillStyle = isPlayed ? COLOURS.caller : COLOURS.idle;
        for (let dot = 0; dot < up; dot++) context.fillRect(x, middle - (dot + 1) * PITCH, DOT, DOT);
        const down = Math.round(level(agent, from, to) * lane);
        context.fillStyle = isPlayed ? COLOURS.agent : COLOURS.idle;
        for (let dot = 0; dot < down; dot++) context.fillRect(x, middle + dot * PITCH + 1, DOT, DOT);
      }
      // The axis, then each reply gap as a bracket under the strip.
      context.fillStyle = COLOURS.idle;
      for (let x = 0; x < width; x += PITCH * 2) context.fillRect(x, middle, DOT, 1);
      context.fillStyle = COLOURS.gap;
      for (const [start, end] of gaps) {
        const x1 = (start / duration) * width;
        const x2 = Math.max(x1 + 2, (end / duration) * width);
        context.fillRect(x1, height - 4, x2 - x1, 1);
        context.fillRect(x1, height - 7, 1, 4);
        context.fillRect(x2 - 1, height - 7, 1, 4);
      }
      const head = Math.min(width - 2, played * width);
      context.fillStyle = COLOURS.head;
      context.shadowColor = "rgba(182, 255, 182, 0.8)";
      context.shadowBlur = 8;
      context.fillRect(head, 0, 2, height - 9);
      context.shadowBlur = 0;
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
  }, [caller, agent, hz, duration, gaps, now, playing]);

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
      className="block h-[4.75rem] w-full cursor-pointer touch-none"
    />
  );
}
