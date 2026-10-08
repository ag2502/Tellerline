// Turn a recorded call into the strip board the replay draws, on the recording's clock.
//
// Each caller turn becomes one strip. It feeds into the bay the moment the caller starts
// speaking; its boxes print as the agent reaches each stage (what Parakeet heard, where the
// router sent it, what Gemma decided, what the bank did), placed from the durations the agent
// measured for that turn between the caller stopping and Tellerline starting to speak; and the
// reply prints in step with Tellerline's voice.

import type { Call, Turn } from "./types";

export const VAD_SILENCE_S = 0.2; // Silero waits for this much quiet before turn detection runs
// Every timing on the page sits on one ruled scale, 0 to this many seconds.
export const SCALE_S = 1.5;

export type Span = [number, number];

export type StageKey = "heard" | "carried" | "exact" | "routed" | "decided" | "held" | "bank";

export type Stage = {
  key: StageKey;
  at: number; // when it prints, seconds from the start of the recording
  label: string;
  value: string;
  ms: number | null;
  tone?: "action" | "held";
};

export type TurnStrip = {
  turn: number;
  feedAt: number; // the caller starts speaking: the strip enters the bay
  caller: { spans: Span[]; text: string; end: number };
  stages: Stage[];
  answeredAt: number; // the agent had its answer
  // The wait from the caller's last word to Tellerline's first, timed at the agent from the
  // recording; `callerWait` is the same wait as the automated caller timed it, WebRTC included.
  // Null when the agent started before the caller had finished.
  wait: { from: number; until: number; callerWait: number | null } | null;
  reply: { spans: Span[]; text: string; at: number } | null;
  carriedOn: boolean;
  raw: Turn;
};

export type Board = {
  greeting: { spans: Span[]; text: string; at: number } | null;
  strips: TurnStrip[];
  gaps: Span[];
  duration: number;
};

const EPSILON = 0.05;

export function describeOutput(turn: Turn): { value: string; tone?: "action" } {
  const output = turn.model.output.trim();
  if (output.startsWith("ACTION")) return { value: output, tone: "action" };
  return { value: "a spoken reply" };
}

export function buildBoard(call: Call): Board {
  const agent = [...call.agent_speaking].sort((a, b) => a[0] - b[0]);
  const caller = [...call.caller_speaking].sort((a, b) => a[0] - b[0]);
  const turns = [...call.turns].sort((a, b) => a.t - b.t);
  const strips: TurnStrip[] = [];
  const gaps: Span[] = [];

  // The greeting: everything Tellerline says before the caller first speaks.
  const firstCaller = caller[0]?.[0] ?? call.duration_s;
  const greetingSpans = agent.filter(([start]) => start < firstCaller);
  const greeting = greetingSpans.length
    ? { spans: greetingSpans, text: call.greeting, at: greetingSpans[0][0] }
    : null;

  let boundary = greetingSpans.length ? greetingSpans[greetingSpans.length - 1][1] : 0;
  for (const turn of turns) {
    // The caller's speech for this turn: what they started saying since the last reply and
    // before the agent answered. It can run past the answer when they talk over the reply.
    let said = caller.filter(([start]) => start >= boundary - EPSILON && start <= turn.t + EPSILON);
    if (!said.length) said = caller.filter(([start]) => start <= turn.t + EPSILON).slice(-1);
    if (!said.length) continue;
    const callerStart = said[0][0];
    const callerEnd = said[said.length - 1][1];

    // The reply is what Tellerline says between the caller stopping and the caller speaking
    // again. It can start just before the turn's report: a pre-rendered opening plays the moment
    // the agent has its answer, before the report is written.
    const lastSaid = said[said.length - 1][0];
    const nextCaller = caller.find(([start]) => start > lastSaid + EPSILON)?.[0] ?? Infinity;
    const reply = agent.filter(
      ([start]) => start >= Math.max(callerStart, turn.t - 0.5 - EPSILON) && start < nextCaller,
    );
    const agentStart = reply[0]?.[0] ?? turn.t;
    const overlap = agentStart < callerEnd;

    // The agent's own measurements, laid out on the recording's clock and finished before it
    // speaks: it can't say a result before it has one.
    const answered = overlap
      ? Math.min(turn.t, agentStart)
      : Math.max(callerEnd + 0.004, Math.min(turn.t, agentStart));
    const heardAt = Math.min(callerEnd + VAD_SILENCE_S + (turn.stt_ms ?? 0) / 1000, answered - 0.004);
    // Routing follows what was heard, even when it all fits in the same few milliseconds.
    const decideStart = Math.max(heardAt + 0.002, answered - (turn.model.ms + (turn.bank?.ms ?? 0)) / 1000);
    const decidedAt = Math.min(decideStart + turn.model.ms / 1000, answered - 0.002);

    const stages: Stage[] = [{ key: "heard", at: heardAt, label: "heard", value: turn.heard, ms: turn.stt_ms }];
    if (turn.carried_on) {
      stages.push({
        key: "carried",
        at: heardAt + 0.0005,
        label: "one turn",
        value: "carried on after a pause before a reply began; both parts answered together",
        ms: null,
        tone: "held",
      });
    }
    if (turn.understood && turn.understood !== turn.heard) {
      stages.push({ key: "exact", at: heardAt + 0.001, label: "exact", value: turn.understood, ms: null });
    }
    const score = turn.route.score === null ? "" : ` (${turn.route.score.toFixed(2)})`;
    stages.push({
      key: "routed",
      at: decideStart,
      label: "routed",
      value: `${turn.route.skill}, ${turn.route.reason}${score}`,
      ms: turn.route.ms,
    });
    const output = describeOutput(turn);
    stages.push({
      key: "decided",
      at: decidedAt,
      label: "decided",
      value: output.value,
      ms: turn.model.ms,
      tone: output.tone,
    });
    if (turn.instead) {
      stages.push({ key: "held", at: decidedAt + 0.001, label: "held back", value: turn.instead, ms: null, tone: "held" });
    }
    if (turn.bank) {
      stages.push({
        key: "bank",
        at: Math.min(decidedAt + turn.bank.ms / 1000, answered - 0.001),
        label: "bank",
        value: turn.bank.outcome,
        ms: turn.bank.ms,
      });
    }

    const hasReply = reply.length > 0;
    if (hasReply && !overlap) gaps.push([callerEnd, agentStart]);
    strips.push({
      turn: turn.turn,
      feedAt: callerStart,
      caller: { spans: said, text: turn.said ?? turn.heard, end: callerEnd },
      stages,
      answeredAt: answered,
      wait:
        hasReply && !overlap
          ? { from: callerEnd, until: agentStart, callerWait: turn.caller_wait_s ?? null }
          : null,
      reply: hasReply ? { spans: reply, text: turn.spoken, at: agentStart } : null,
      carriedOn: Boolean(turn.carried_on),
      raw: turn,
    });
    boundary = hasReply ? Math.max(callerEnd, reply[reply.length - 1][1]) : callerEnd;
  }

  return { greeting, strips, gaps, duration: call.duration_s };
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

/** Where `seconds` sits on the page's one scale, as a share of its width (0 to 1). */
export function onScale(seconds: number): number {
  return Math.max(0, Math.min(1, seconds / SCALE_S));
}
