import type { Board } from "@/lib/timeline";
import type { Call } from "@/lib/types";

// Where every fin wants to be for each bay's stage. A formation writes targets only; the scene
// eases the fins toward them. Every shape is the page's own data, measured or recorded.

export type SlotRect = { x: number; y: number; width: number; height: number }; // world units, centre

type Targets = { position: Float32Array; scale: Float32Array; color: Float32Array };

export type Formation = {
  data: {
    histogram: { from: number; count: number }[];
    turn: { hearEnd: number; total: number; p50: number; p90: number };
    memory: { name: string; gb: number; tone: "decide" | "hear" | "speak" | "route" }[];
  };
};

type Input = {
  data: Formation["data"];
  rect: SlotRect;
  count: number;
  time: number;
  target: Targets;
  now: number;
  playing: boolean;
  board: Board | null;
  call: Call | null;
  reduced: boolean;
  pointer: { x: number; y: number; inside: boolean }; // world units, over the stage
  pixels: number; // the stage's width in CSS pixels
};

const SCALE_S = 1.5;
const GB = 16;

const hex = (value: string): [number, number, number] => [
  parseInt(value.slice(1, 3), 16) / 255,
  parseInt(value.slice(3, 5), 16) / 255,
  parseInt(value.slice(5, 7), 16) / 255,
];

export const COLOURS = {
  amber: hex("#f2c14e"),
  amberPale: hex("#b3aa92"), // uninked: bare aluminium, warm side
  blue: hex("#2f6fd6"),
  bluePale: hex("#949fae"), // uninked: bare aluminium, cool side
  blueLight: hex("#a9c3ef"),
  blueInk: hex("#1f57b5"),
  ink: hex("#16191d"),
  ink3: hex("#5b646e"),
  pale: hex("#d5dadf"),
  red: hex("#d93a2b"),
};

function put(target: Targets, i: number, x: number, y: number, z: number, sx: number, sy: number, sz: number, colour: [number, number, number]) {
  const j = i * 3;
  target.position[j] = x;
  target.position[j + 1] = y;
  target.position[j + 2] = z;
  target.scale[j] = sx;
  target.scale[j + 1] = sy;
  target.scale[j + 2] = sz;
  target.color[j] = colour[0];
  target.color[j + 1] = colour[1];
  target.color[j + 2] = colour[2];
}

function hide(target: Targets, from: number, count: number, rect: SlotRect) {
  for (let i = from; i < count; i++) put(target, i, rect.x, rect.y - rect.height * 0.5, 0, 0.0001, 0.0001, 0.0001, COLOURS.pale);
}

function level(values: number[], hz: number, from: number, to: number): number {
  let peak = 0;
  const start = Math.max(0, Math.floor(from * hz));
  const end = Math.min(values.length, Math.max(start + 1, Math.ceil(to * hz)));
  for (let i = start; i < end; i++) peak = Math.max(peak, values[i]);
  return peak / 255;
}

// The hero: the recorded call left to right, the caller above the line in amber and Tellerline
// below in blue, inked in as it plays. Each wait is a bead on the line; the live one is red.
function hero({ rect, count, time, target, now, playing, board, call, reduced, pointer, pixels }: Input) {
  // About one column per 6 px, so a phone's fins stay solid rather than hairlines.
  const columns = Math.min(Math.floor(count / 2), Math.max(40, Math.floor(pixels / 6)));
  if (!call || !board) return hide(target, 0, count, rect);
  const duration = call.duration_s;
  const span = rect.width * 0.96;
  const width = span / columns;
  const gap = rect.height * 0.018;
  const liveCaller = playing ? level(call.envelope.caller, call.envelope_hz, now - 0.08, now + 0.08) : 0;
  const liveAgent = playing ? level(call.envelope.agent, call.envelope_hz, now - 0.08, now + 0.08) : 0;
  for (let c = 0; c < columns; c++) {
    const from = (c / columns) * duration;
    const to = ((c + 1) / columns) * duration;
    const middle = (from + to) / 2;
    const x = rect.x - span / 2 + (c + 0.5) * width;
    const bend = (c / (columns - 1)) * 2 - 1;
    const z = -bend * bend * 1.6;
    const played = middle <= now;
    const wait = board.gaps.find(([start, end]) => middle >= start && middle <= end);
    if (wait) {
      const live = now >= wait[0] && now <= wait[1] + 1.2;
      const bead = width * 0.7;
      put(target, c * 2, x, rect.y, z, bead, bead, bead, live && playing ? COLOURS.red : played ? COLOURS.ink : COLOURS.ink3);
      put(target, c * 2 + 1, x, rect.y, z, 0.0001, 0.0001, 0.0001, COLOURS.pale);
      continue;
    }
    const near = playing ? Math.max(0, 1 - Math.abs(middle - now) / 1.4) : 0;
    const breathe = reduced ? 1 : 1 + 0.07 * Math.sin(time * 1.3 + c * 0.23);
    const reach = 0.47 * rect.height;
    // The pointer lifts the fins it passes over, like a hand over the keys.
    const lift = pointer.inside && !reduced ? Math.max(0, 1 - Math.abs(x - pointer.x) / (rect.width * 0.06)) * 0.14 * rect.height : 0;
    const up = Math.min(reach, (0.025 + 0.36 * level(call.envelope.caller, call.envelope_hz, from, to) + 0.12 * liveCaller * near) * rect.height * breathe);
    const down = Math.min(reach, (0.025 + 0.36 * level(call.envelope.agent, call.envelope_hz, from, to) + 0.12 * liveAgent * near) * rect.height * breathe);
    put(target, c * 2, x, rect.y + gap + (up + lift) / 2, z + lift * 0.6, width * 0.6, up + lift, width * 1.1, played ? COLOURS.amber : COLOURS.amberPale);
    put(target, c * 2 + 1, x, rect.y - gap - (down + lift) / 2, z + lift * 0.6, width * 0.6, down + lift, width * 1.1, played ? COLOURS.blue : COLOURS.bluePale);
  }
  hide(target, columns * 2, count, rect);
}

// One turn on the page's scale: hearing the caller in amber, deciding and answering in blue,
// then the rest of the wait the caller hears, to half and to nine in ten of the replies.
function turn({ data, rect, count, time, target, reduced }: Input) {
  const columns = Math.floor(count / 2);
  const width = rect.width / columns;
  const { hearEnd, total, p50, p90 } = data.turn;
  for (let c = 0; c < columns; c++) {
    const at = ((c + 0.5) / columns) * SCALE_S;
    const x = rect.x - rect.width / 2 + (c + 0.5) * width;
    const [height, colour] =
      at < hearEnd
        ? [0.86, COLOURS.amber]
        : at < total
          ? [0.86, COLOURS.blue]
          : at < p50
            ? [0.56, COLOURS.bluePale]
            : at < p90
              ? [0.34, COLOURS.bluePale]
              : [0.08, COLOURS.pale];
    const wave = reduced ? 1 : 1 + 0.05 * Math.sin(time * 1.6 - c * 0.18);
    const half = (rect.height * height * wave) / 2;
    put(target, c * 2, x, rect.y + half / 2 + 0.02, 0, width * 0.62, half, width * 1.2, colour);
    put(target, c * 2 + 1, x, rect.y - half / 2 - 0.02, 0, width * 0.62, half, width * 1.2, colour);
  }
  hide(target, columns * 2, count, rect);
}

// Every timed reply of the gate as one block, stacked by the caller's wait on the page's scale;
// replies past the target share the column beyond its end.
function numbers({ data, rect, count, time, target, reduced }: Input) {
  const columns = 16;
  const width = rect.width / columns;
  const stacks = new Array(columns).fill(0);
  for (const bin of data.histogram) {
    const column = bin.from >= SCALE_S - 1e-9 ? columns - 1 : Math.round(bin.from / 0.1);
    stacks[Math.min(columns - 1, column)] += bin.count;
  }
  const tallest = Math.max(...stacks);
  const step = (rect.height * 0.94) / tallest;
  let i = 0;
  for (let c = 0; c < columns && i < count; c++) {
    for (let k = 0; k < stacks[c] && i < count; k++, i++) {
      const bob = reduced ? 0 : Math.sin(time * 1.2 + c * 0.5 + k * 0.08) * step * 0.08;
      put(
        target,
        i,
        rect.x - rect.width / 2 + (c + 0.5) * width,
        rect.y - rect.height / 2 + (k + 0.5) * step + bob,
        0,
        width * 0.74,
        step * 0.72,
        width * 0.5,
        c === columns - 1 ? COLOURS.ink3 : COLOURS.blue,
      );
    }
  }
  hide(target, i, count, rect);
}

// The Mac's 16 GB as a chip of tenths: what the four models hold, the rest left for everything else.
function memory({ data, rect, count, time, target, reduced }: Input) {
  const columns = 20;
  const rows = 8;
  const cell = Math.min(rect.width / columns, rect.height / rows);
  const tiles: [number, number, number][] = [];
  const tone = { decide: COLOURS.blue, hear: COLOURS.amber, speak: COLOURS.blueLight, route: COLOURS.ink };
  for (const model of data.memory) for (let n = 0; n < Math.round(model.gb * 10); n++) tiles.push(tone[model.tone]);
  const total = (GB * 10) / 1;
  let i = 0;
  for (let n = 0; n < total && i < count; n++, i++) {
    const c = n % columns;
    const r = Math.floor(n / columns);
    const filled = n < tiles.length;
    const lift = reduced ? 0 : filled ? 0.18 + 0.08 * Math.sin(time * 1.5 + n * 0.3) : 0;
    put(
      target,
      i,
      rect.x - (columns * cell) / 2 + (c + 0.5) * cell,
      rect.y + (rows * cell) / 2 - (r + 0.5) * cell,
      lift * cell * 2,
      cell * 0.84,
      cell * 0.84,
      cell * (filled ? 0.7 : 0.22),
      filled ? tiles[n] : COLOURS.pale,
    );
  }
  hide(target, i, count, rect);
}

export const formations = { hero, turn, numbers, memory };
