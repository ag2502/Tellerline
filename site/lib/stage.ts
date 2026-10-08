import type { Board } from "./timeline";
import type { Call } from "./types";

// What the 3D stage reads every frame, written by the call's clock and the page around it. A
// plain object rather than React state: the scene samples it sixty times a second without
// re-rendering anything.
export const stage = {
  now: 0, // the call's clock, seconds
  playing: false,
  call: null as Call | null,
  board: null as Board | null,
  reduced: false, // prefers-reduced-motion: the scene holds still
  pointer: { x: 0, y: 0 }, // -1 to 1 across the viewport
};
