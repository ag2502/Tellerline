"use client";

import { useEffect, useRef } from "react";

import { useCall } from "./CallContext";

// The call as light: a ring of bars reading the recorded voices a second and a half either side
// of the playhead, teal where the caller is louder and coral where Tellerline is, around a core
// that swells with whoever is speaking. At rest it breathes. It draws only while it is on screen.

const BARS = 112;
const TEAL = [79, 227, 200];
const CORAL = [255, 107, 139];

function peak(values: number[], hz: number, from: number, to: number): number {
  const start = Math.max(0, Math.floor(from * hz));
  const end = Math.min(values.length, Math.max(start + 1, Math.ceil(to * hz)));
  let top = 0;
  for (let i = start; i < end; i++) top = Math.max(top, values[i]);
  return top / 255;
}

export function Orb({ className }: { className?: string }) {
  const { call, nowRef, playing, reducedMotion } = useCall();
  const canvas = useRef<HTMLCanvasElement>(null);
  const live = useRef({ call, playing });
  live.current = { call, playing };

  useEffect(() => {
    const element = canvas.current;
    const context = element?.getContext("2d");
    if (!element || !context) return;
    let visible = true;
    let frame = 0;
    let size = 0;
    let caller = 0;
    let agent = 0;
    let last = 0;

    const fit = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      size = element.clientWidth;
      element.width = Math.round(size * ratio);
      element.height = Math.round(size * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    const draw = (time: number) => {
      const { call: current, playing: on } = live.current;
      const now = nowRef.current ?? 0;
      const seconds = time / 1000;
      const hz = current.envelope_hz;
      const wantCaller = on ? peak(current.envelope.caller, hz, now - 0.1, now + 0.1) : 0.06 + 0.04 * Math.sin(seconds * 1.1);
      const wantAgent = on ? peak(current.envelope.agent, hz, now - 0.1, now + 0.1) : 0.06 + 0.04 * Math.sin(seconds * 0.9 + 2);
      caller += (wantCaller - caller) * 0.25;
      agent += (wantAgent - agent) * 0.25;

      const c = size / 2;
      context.clearRect(0, 0, size, size);
      // The core: two lights that swell with their voice.
      for (const [level, rgb, dx] of [[caller, TEAL, -0.07], [agent, CORAL, 0.07]] as const) {
        const radius = size * (0.2 + level * 0.2);
        const gradient = context.createRadialGradient(c + size * dx, c, 0, c + size * dx, c, radius);
        gradient.addColorStop(0, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${0.55 + level * 0.4})`);
        gradient.addColorStop(1, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0)`);
        context.fillStyle = gradient;
        context.fillRect(0, 0, size, size);
      }
      // The ring of bars.
      const inner = size * 0.27;
      context.lineCap = "round";
      context.lineWidth = Math.max(2, size * 0.0085);
      for (let i = 0; i < BARS; i++) {
        const share = i / BARS;
        const angle = share * Math.PI * 2 - Math.PI / 2;
        // Mirrored left and right, so the playhead sits at the top and the ring reads as a pair.
        const offset = (Math.abs(share - 0.5) * 2 - 0.5) * 3;
        let a: number;
        let b: number;
        if (on) {
          a = peak(current.envelope.caller, hz, now + offset - 0.05, now + offset + 0.05);
          b = peak(current.envelope.agent, hz, now + offset - 0.05, now + offset + 0.05);
        } else {
          const wave = 0.5 + 0.5 * Math.sin(share * Math.PI * 6 + seconds * 0.8);
          a = 0.06 + 0.12 * wave;
          b = 0.06 + 0.1 * (1 - wave);
        }
        const level = Math.max(a, b);
        const rgb = a >= b ? TEAL : CORAL;
        const length = size * (0.012 + level * 0.15);
        context.strokeStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${0.4 + level * 0.6})`;
        context.beginPath();
        context.moveTo(c + Math.cos(angle) * inner, c + Math.sin(angle) * inner);
        context.lineTo(c + Math.cos(angle) * (inner + length), c + Math.sin(angle) * (inner + length));
        context.stroke();
      }
      // A thin ring under the bars.
      context.strokeStyle = "rgba(244,241,255,0.14)";
      context.lineWidth = 1;
      context.beginPath();
      context.arc(c, c, inner - size * 0.02, 0, Math.PI * 2);
      context.stroke();
    };

    const loop = (time: number) => {
      frame = 0;
      if (!visible) return;
      // Resting, it breathes at half rate; playing, it follows every frame.
      if (live.current.playing || time - last > 33) {
        last = time;
        draw(time);
      }
      if (!reducedMotion || live.current.playing) frame = requestAnimationFrame(loop);
    };
    const start = () => {
      if (!frame) frame = requestAnimationFrame(loop);
    };

    fit();
    draw(0);
    start();
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) start();
    });
    observer.observe(element);
    const resize = new ResizeObserver(() => {
      fit();
      draw(performance.now());
    });
    resize.observe(element);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      resize.disconnect();
    };
  }, [nowRef, reducedMotion, playing]);

  return <canvas ref={canvas} aria-hidden="true" className={className ?? "block aspect-square w-full"} />;
}
