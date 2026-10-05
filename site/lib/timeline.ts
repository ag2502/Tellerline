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

// A gap is timed at the agent, from the recording; `callerWait` is the same wait as the caller
// timed it, which includes the audio's trip over WebRTC both ways.
export type GapLine = {
  kind: "gap";
  at: number;
  until: number;
  turn: number;
  callerWait: number | null;
};

export type Line = SpeechLine | StageLine | GapLine;

export type Timeline = { lines: Line[]; gaps: Span[]; duration: number };

const EPSILON = 0.05;

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
  turns.forEach((turn) => {
    // The caller's speech for this turn: what they started saying since the last reply and
    // before the agent answered. It can run past the answer when they talk over the reply.
    let said = caller.filter(
      ([start]) => start >= boundary - EPSILON && start <= turn.t + EPSILON,
    );
    if (!said.length) said = caller.filter(([start]) => start <= turn.t + EPSILON).slice(-1);
    if (!said.length) return;
    const callerStart = said[0][0];
    const callerEnd = said[said.length - 1][1];
    // What the caller said (from the script, when the call had one); what Parakeet heard is
    // the turn's first stage line.
    const words = turn.said ?? turn.heard;
    lines.push({ kind: "caller", at: said[0][0], spans: said, text: words, turn: turn.turn });

    // The reply is what Tellerline says between the caller stopping and the caller speaking
    // again. It can start just before the turn's report: a pre-rendered opening plays the moment
    // the agent has its answer, before the report is written.
    const lastSaid = said[said.length - 1][0];
    const nextCaller = caller.find(([start]) => start > lastSaid + EPSILON)?.[0] ?? Infinity;
    const reply = agent.filter(
      ([start]) =>
        start >= Math.max(callerStart, turn.t - 0.5 - EPSILON) && start < nextCaller,
    );
    const agentStart = reply[0]?.[0] ?? turn.t;
    // The agent started before the caller had finished: an overlap, with no wait to show.
    const overlap = agentStart < callerEnd;

    // The agent's own measurements, laid out on the recording's clock and finished before it
    // speaks: it can't say a result before it has one.
    const answered = overlap
      ? Math.min(turn.t, agentStart)
      : Math.max(callerEnd + 0.004, Math.min(turn.t, agentStart));
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
      if (!overlap) {
        lines.push({
          kind: "gap",
          at: callerEnd,
          until: agentStart,
          turn: turn.turn,
          callerWait: turn.caller_wait_s ?? null,
        });
        gaps.push([callerEnd, agentStart]);
      }
      lines.push({ kind: "agent", at: agentStart, spans: reply, text: turn.spoken, turn: turn.turn });
      boundary = Math.max(callerEnd, reply[reply.length - 1][1]);
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
