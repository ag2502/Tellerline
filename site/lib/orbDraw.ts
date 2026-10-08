import type { Call } from "./types";

// The orb's drawing, shared by the page's live orb and the film's frames: a ring of bars reading
// the recorded voices a second and a half either side of the playhead, teal where the caller is
// louder and coral where Tellerline is, around a core that swells with whoever is speaking.

const BARS = 112;
const TEAL = [79, 227, 200];
const CORAL = [255, 107, 139];

export type OrbState = { caller: number; agent: number; power: number; x: number; y: number; on: boolean };

export const newOrbState = (): OrbState => ({ caller: 0, agent: 0, power: 0, x: 0, y: 0, on: false });

function peak(values: number[], hz: number, from: number, to: number): number {
  const start = Math.max(0, Math.floor(from * hz));
  const end = Math.min(values.length, Math.max(start + 1, Math.ceil(to * hz)));
  let top = 0;
  for (let i = start; i < end; i++) top = Math.max(top, values[i]);
  return top / 255;
}

// `seconds` drives the resting breath; `smooth` is how fast the core follows the voices (1 = at
// once, as a film frame wants).
export function drawOrb(context: CanvasRenderingContext2D, size: number, call: Call, now: number, playing: boolean, seconds: number, state: OrbState, smooth = 0.25) {
  const hz = call.envelope_hz;
  const wantCaller = playing ? peak(call.envelope.caller, hz, now - 0.1, now + 0.1) : 0.06 + 0.04 * Math.sin(seconds * 1.1);
  const wantAgent = playing ? peak(call.envelope.agent, hz, now - 0.1, now + 0.1) : 0.06 + 0.04 * Math.sin(seconds * 0.9 + 2);
  state.power += ((state.on ? 1 : 0) - state.power) * 0.12;
  state.caller += (wantCaller - state.caller) * smooth;
  state.agent += (wantAgent - state.agent) * smooth;

  const c = size / 2;
  context.clearRect(0, 0, size, size);
  const pull = state.power * 0.05;
  const shiftX = (state.x / (size / 2)) * pull * size;
  const shiftY = (state.y / (size / 2)) * pull * size;
  for (const [level, rgb, dx] of [[state.caller, TEAL, -0.07], [state.agent, CORAL, 0.07]] as const) {
    const radius = size * (0.2 + level * 0.2);
    const gx = c + size * dx + shiftX;
    const gradient = context.createRadialGradient(gx, c + shiftY, 0, gx, c + shiftY, radius);
    gradient.addColorStop(0, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${0.55 + level * 0.4})`);
    gradient.addColorStop(1, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0)`);
    context.fillStyle = gradient;
    context.fillRect(0, 0, size, size);
  }
  const inner = size * 0.27;
  const aim = Math.atan2(state.y, state.x);
  const near = Math.min(1, (Math.hypot(state.x, state.y) / (size / 2)) * 1.3);
  context.lineCap = "round";
  context.lineWidth = Math.max(2, size * 0.0085);
  for (let i = 0; i < BARS; i++) {
    const share = i / BARS;
    const angle = share * Math.PI * 2 - Math.PI / 2;
    // Mirrored left and right, so the playhead sits at the top and the ring reads as a pair.
    const offset = (Math.abs(share - 0.5) * 2 - 0.5) * 3;
    let a: number;
    let b: number;
    if (playing) {
      a = peak(call.envelope.caller, hz, now + offset - 0.05, now + offset + 0.05);
      b = peak(call.envelope.agent, hz, now + offset - 0.05, now + offset + 0.05);
    } else {
      const wave = 0.5 + 0.5 * Math.sin(share * Math.PI * 6 + seconds * 0.8);
      a = 0.06 + 0.12 * wave;
      b = 0.06 + 0.1 * (1 - wave);
    }
    const level = Math.max(a, b);
    const rgb = a >= b ? TEAL : CORAL;
    // The bars lean out toward the pointer.
    let apart = Math.abs(angle - aim) % (Math.PI * 2);
    if (apart > Math.PI) apart = Math.PI * 2 - apart;
    const bulge = state.power * Math.exp(-(apart * apart) / 0.16) * size * 0.07 * (0.3 + 0.7 * near);
    const length = size * (0.012 + level * 0.15) + bulge;
    context.strokeStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${0.4 + level * 0.6})`;
    context.beginPath();
    context.moveTo(c + Math.cos(angle) * inner, c + Math.sin(angle) * inner);
    context.lineTo(c + Math.cos(angle) * (inner + length), c + Math.sin(angle) * (inner + length));
    context.stroke();
  }
  context.strokeStyle = "rgba(244,241,255,0.14)";
  context.lineWidth = 1;
  context.beginPath();
  context.arc(c, c, inner - size * 0.02, 0, Math.PI * 2);
  context.stroke();
}
