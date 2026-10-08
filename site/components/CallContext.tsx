"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { type Board, buildBoard } from "@/lib/timeline";
import type { Call, CallSummary } from "@/lib/types";
import { useReducedMotion } from "@/lib/useReducedMotion";

// The recorded call and its one clock, shared by the hero's stage, the strip board and the 3D
// scene. The audio element is the clock: pause it and everything that reads it freezes.

type CallState = {
  calls: CallSummary[];
  call: Call;
  board: Board;
  now: number;
  nowRef: React.RefObject<number>;
  playing: boolean;
  buffering: boolean;
  started: boolean;
  finished: boolean;
  loading: string | null;
  failed: string | null;
  reducedMotion: boolean;
  toggle: () => Promise<void>;
  pause: () => void;
  seek: (seconds: number) => void;
  choose: (slug: string) => Promise<void>;
  playCall: (slug: string) => Promise<void>;
};

const CallContext = createContext<CallState | null>(null);

export function useCall(): CallState {
  const state = useContext(CallContext);
  if (!state) throw new Error("useCall outside CallProvider");
  return state;
}

export function CallProvider({ calls, initial, children }: { calls: CallSummary[]; initial: Call; children: React.ReactNode }) {
  const reducedMotion = useReducedMotion();
  const [call, setCall] = useState<Call>(initial);
  const [loading, setLoading] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [buffering, setBuffering] = useState(false);
  const [started, setStarted] = useState(false);
  const [now, setNow] = useState(0);
  const nowRef = useRef(0);
  const audio = useRef<HTMLAudioElement>(null);
  const cache = useRef(new Map<string, Call>([[initial.slug, initial]]));
  const board = useMemo(() => buildBoard(call), [call]);


  // React redraws about sixteen times a second while the call plays; the waveform and the 3D
  // stage read the same clock every frame.
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    let last = 0;
    const tick = (time: number) => {
      if (audio.current) nowRef.current = audio.current.currentTime;
      if (time - last > 60) {
        last = time;
        setNow(nowRef.current);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing]);

  const toggle = useCallback(async () => {
    const element = audio.current;
    if (!element) return;
    if (!element.paused) {
      element.pause();
      return;
    }
    if (element.ended || element.currentTime >= call.duration_s - 0.05) {
      element.currentTime = 0;
      nowRef.current = 0;
      setNow(0);
    }
    setStarted(true);
    try {
      await element.play();
    } catch {
      setPlaying(false);
    }
  }, [call.duration_s]);

  const pause = useCallback(() => audio.current?.pause(), []);

  const seek = useCallback((seconds: number) => {
    const element = audio.current;
    if (!element) return;
    element.currentTime = seconds;
    nowRef.current = seconds;
    setNow(seconds);
    setStarted(true);
  }, []);

  const choose = useCallback(
    async (slug: string) => {
      if (slug === call.slug && !failed) return;
      audio.current?.pause();
      setFailed(null);
      let next = cache.current.get(slug);
      if (!next) {
        setLoading(slug);
        try {
          const response = await fetch(`/calls/${slug}.json`);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          next = (await response.json()) as Call;
          cache.current.set(slug, next);
        } catch {
          setFailed(slug);
          setLoading(null);
          return;
        }
        setLoading(null);
      }
      nowRef.current = 0;
      setNow(0);
      setStarted(false);
      setPlaying(false);
      setCall(next);
    },
    [call.slug, failed],
  );

  // Playing another call starts it once it has loaded.
  const pendingPlay = useRef(false);
  useEffect(() => {
    if (pendingPlay.current) {
      pendingPlay.current = false;
      void toggle();
    }
  }, [call, toggle]);

  const playCall = useCallback(
    async (slug: string) => {
      if (slug === call.slug) {
        if (audio.current?.paused) await toggle();
        return;
      }
      pendingPlay.current = true;
      await choose(slug);
    },
    [call.slug, choose, toggle],
  );

  // Space plays or pauses the call when nothing else has the keyboard and the call is in view.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (event.key !== " " || target.closest("button, a, input, textarea, summary, [role=slider]")) return;
      const panes = ["top", "call"].map((id) => document.getElementById(id)).filter(Boolean) as HTMLElement[];
      const visible = panes.some((pane) => {
        const rect = pane.getBoundingClientRect();
        return rect.bottom > 0 && rect.top < window.innerHeight;
      });
      if (!visible) return;
      event.preventDefault();
      void toggle();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  const finished = started && !playing && now >= call.duration_s - 0.05;

  const value: CallState = {
    calls,
    call,
    board,
    now,
    nowRef,
    playing,
    buffering,
    started,
    finished,
    loading,
    failed,
    reducedMotion,
    toggle,
    pause,
    seek,
    choose,
    playCall,
  };

  return (
    <CallContext.Provider value={value}>
      {children}
      <audio
        ref={audio}
        src={call.audio}
        preload="none"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          setPlaying(false);
          nowRef.current = call.duration_s;
          setNow(call.duration_s);
        }}
        onWaiting={() => setBuffering(true)}
        onPlaying={() => setBuffering(false)}
      />
    </CallContext.Provider>
  );
}
