"use client";

import { useEffect, useRef } from "react";

import { drawOrb, newOrbState } from "@/lib/orbDraw";

import { useCall } from "./CallContext";

// The call as light: a ring of bars reading the recorded voices a second and a half either side
// of the playhead, teal where the caller is louder and coral where Tellerline is, around a core
// that swells with whoever is speaking. At rest it breathes. It draws only while it is on screen.

export function Orb({ className }: { className?: string }) {
  const { call, nowRef, playing, reducedMotion } = useCall();
  const canvas = useRef<HTMLCanvasElement>(null);
  const live = useRef({ call, playing });
  const pointer = useRef(newOrbState());
  live.current = { call, playing };

  useEffect(() => {
    const element = canvas.current;
    const context = element?.getContext("2d");
    if (!element || !context) return;
    let visible = true;
    let frame = 0;
    let size = 0;
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
      drawOrb(context, size, current, nowRef.current ?? 0, on, time / 1000, pointer.current);
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

    const onMove = (event: PointerEvent) => {
      const box = element.getBoundingClientRect();
      const x = event.clientX - (box.left + box.width / 2);
      const y = event.clientY - (box.top + box.height / 2);
      pointer.current.x = x;
      pointer.current.y = y;
      pointer.current.on = true;
      // The whole orb turns a few degrees toward you.
      const tiltX = Math.max(-1, Math.min(1, y / box.height)) * -10;
      const tiltY = Math.max(-1, Math.min(1, x / box.width)) * 10;
      element.style.transform = `perspective(900px) rotateX(${tiltX}deg) rotateY(${tiltY}deg)`;
      start();
    };
    const onLeave = () => {
      pointer.current.on = false;
      element.style.transform = "";
    };
    if (window.matchMedia("(pointer: fine)").matches) {
      element.addEventListener("pointermove", onMove);
      element.addEventListener("pointerleave", onLeave);
    }

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
      element.removeEventListener("pointermove", onMove);
      element.removeEventListener("pointerleave", onLeave);
      observer.disconnect();
      resize.disconnect();
    };
  }, [nowRef, reducedMotion, playing]);

  return <canvas ref={canvas} aria-hidden="true" className={className ?? "block aspect-square w-full cursor-pointer transition-transform duration-200 ease-out"} />;
}
