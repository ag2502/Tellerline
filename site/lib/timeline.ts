// Turn a recorded call into the lines the replay prints, each on the recording's clock.
//
// Speech lines reveal in step with the voice: a line spoken over [start, end] intervals shows
// the share of its characters that the voice has reached. Stage lines (what Parakeet heard,
// the route, Gemma's answer, the bank) are placed from the durations the agent measured for
// that turn, between the moment the caller stopped and the moment Tellerline started speaking.

import type { Call, Turn } from "./types";

export const VAD_SILENCE_S = 0.2; // Silero waits for this much quiet before turn detection runs

export type Span = [number, number];

export type SpeechLine = {
  kind: "agent" | "caller";
  at: number;
  spans: Span[];
  text: string;
  turn: number | null;
};

export type StageLine = {
  kind: "stage";
  at: number;
  label: string;
  value: string;
  ms: number | null;
  turn: number;
  tone?: "action" | "held";
};

export type GapLine = { kind: "gap"; at: number; until: number; turn: number };

export type Line = SpeechLine | StageLine | GapLine;

export type Timeline = { lines: Line[]; gaps: Span[]; duration: number };

const EPSILON = 0.05;

function spansBetween(spans: Span[], from: number, to: number): Span[] {
  return spans.filter(([start]) => start >= from - EPSILON && start < to);
}

export function describeOutput(turn: Turn): { value: string; tone?: "action" | "held" } {
  const output = turn.model.output.trim();
  if (output.startsWith("ACTION")) return { value: output, tone: "action" };
  return { value: "a spoken reply" };
}

export function buildTimeline(call: Call): Timeline {
  const agent = [...call.agent_speaking].sort((a, b) => a[0] - b[0]);
  const caller = [...call.caller_speaking].sort((a, b) => a[0] - b[0]);
  const turns = [...call.turns].sort((a, b) => a.t - b.t);
  const lines: Line[] = [];
  const gaps: Span[] = [];

  // The greeting: everything Tellerline says before the caller first speaks.
  const firstCaller = caller[0]?.[0] ?? call.duration_s;
  const greeting = agent.filter(([start]) => start < firstCaller);
  if (greeting.length) {
    lines.push({ kind: "agent", at: greeting[0][0], spans: greeting, text: call.greeting, turn: null });
  }

  let boundary = greeting.length ? greeting[greeting.length - 1][1] : 0;
  turns.forEach((turn, index) => {
    const next = turns[index + 1]?.t ?? call.duration_s + 1;
    let said = caller.filter(([start, end]) => start >= boundary - EPSILON && end <= turn.t + EPSILON);
    if (!said.length) said = caller.filter(([, end]) => end <= turn.t + EPSILON).slice(-1);
    if (!said.length) return;
    const callerEnd = said[said.length - 1][1];
    lines.push({ kind: "caller", at: said[0][0], spans: said, text: turn.heard, turn: turn.turn });

    // The reply starts at or just before the turn's report: a pre-rendered opening starts
    // playing the moment the agent has its answer, before the report is written.
    const reply = spansBetween(agent, turn.t - 0.5, next).filter(([start]) => start >= callerEnd);
    const agentStart = reply[0]?.[0] ?? turn.t;

    // The agent's own measurements, laid out on the recording's clock and finished before it
    // speaks: it can't say a result before it has one.
    const answered = Math.max(callerEnd + 0.004, Math.min(turn.t, agentStart));
    const heardAt = Math.min(callerEnd + VAD_SILENCE_S + (turn.stt_ms ?? 0) / 1000, answered - 0.004);
    const decideStart = Math.max(
      heardAt,
      answered - (turn.model.ms + (turn.bank?.ms ?? 0)) / 1000,
    );
    const decidedAt = Math.min(decideStart + turn.model.ms / 1000, answered - 0.002);
    lines.push({
      kind: "stage",
      at: heardAt,
      label: "heard",
      value: `"${turn.heard}"`,
      ms: turn.stt_ms,
      turn: turn.turn,
    });
    if (turn.understood && turn.understood !== turn.heard) {
      lines.push({
        kind: "stage",
        at: heardAt + 0.001,
        label: "exact",
        value: `"${turn.understood}"`,
        ms: null,
        turn: turn.turn,
      });
    }
    const score = turn.route.score === null ? "" : ` (${turn.route.score.toFixed(2)})`;
    lines.push({
      kind: "stage",
      at: decideStart,
      label: "routed",
      value: `${turn.route.skill} skill, ${turn.route.reason}${score}`,
      ms: turn.route.ms,
      turn: turn.turn,
    });
    const output = describeOutput(turn);
    lines.push({
      kind: "stage",
      at: decidedAt,
      label: "decided",
      value: output.value,
      ms: turn.model.ms,
      turn: turn.turn,
      tone: output.tone,
    });
    if (turn.instead) {
      lines.push({
        kind: "stage",
        at: decidedAt + 0.001,
        label: "held back",
        value: turn.instead,
        ms: null,
        turn: turn.turn,
        tone: "held",
      });
    }
    if (turn.bank) {
      lines.push({
        kind: "stage",
        at: Math.min(decidedAt + turn.bank.ms / 1000, answered - 0.001),
        label: "bank",
        value: turn.bank.outcome,
        ms: turn.bank.ms,
        turn: turn.turn,
      });
    }
    if (reply.length) {
      lines.push({ kind: "gap", at: callerEnd, until: agentStart, turn: turn.turn });
      gaps.push([callerEnd, agentStart]);
      lines.push({ kind: "agent", at: agentStart, spans: reply, text: turn.spoken, turn: turn.turn });
      boundary = reply[reply.length - 1][1];
    } else {
      boundary = callerEnd;
    }
  });

  lines.sort((a, b) => a.at - b.at);
  return { lines, gaps, duration: call.duration_s };
}

/** How much of a line spoken over ``spans`` has been said by time ``t`` (0 to 1). */
export function spokenShare(spans: Span[], t: number): number {
  let total = 0;
  let done = 0;
  for (const [start, end] of spans) {
    const length = Math.max(0, end - start);
    total += length;
    done += Math.min(length, Math.max(0, t - start));
  }
  return total > 0 ? done / total : 1;
}

export function clock(seconds: number): string {
  const whole = Math.max(0, seconds);
  const minutes = Math.floor(whole / 60);
  const rest = whole - minutes * 60;
  return `${String(minutes).padStart(2, "0")}:${rest.toFixed(1).padStart(4, "0")}`;
}
