// Shapes of the files scripts/export_site_data.py writes from real runs and recordings.

export type Spread = { n: number; p50: number; p90: number; p95: number; max: number };

export type CallerRun = {
  file: string;
  calls: number;
  turns: number;
  measured: number;
  overlaps: number;
  without_reply: number;
  concurrency: number;
  background_db: number | null;
  latency_s: Spread | null;
  histogram: { from: number; to: number; count: number }[];
  stages_ms: Record<string, { p50: number; p90: number }>;
  machine: {
    chip: string;
    memory_gb: number;
    power?: { on_battery: boolean; battery_percent: number | null; low_power_mode: boolean };
    memory?: { swap_used_gb: number | null; compressed_gb: number | null };
  };
  started_at: string;
};

export type Accuracy = {
  single_turn: number;
  dialogue_turns: number;
  dialogues: number;
  reply_p90_ms?: number;
  action_p90_ms?: number;
  failures?: string[];
  file: string;
};

export type Decision = {
  id: string;
  title: string;
  date: string;
  note: string;
  decision?: string;
  why?: string;
  result?: string;
  considered?: string;
};

export type CallSummary = { slug: string; title: string; summary: string; duration_s: number };

export type SiteData = {
  generated_at: string;
  live: {
    gate?: CallerRun;
    capacity: CallerRun[];
    noisy?: CallerRun;
    phone?: CallerRun;
    before?: CallerRun;
  };
  accuracy: {
    dev?: Accuracy;
    test?: Accuracy;
    holdout?: Accuracy;
    holdout_before?: Accuracy;
    counts: Record<string, { cases: number; dialogues: number }>;
  };
  first_audio: {
    sentence: { p50: number; p90: number };
    clause: { p50: number; p90: number };
    clause_cached: { p50: number; p90: number };
    file: string;
  } | null;
  memory: Record<
    string,
    { weights_gb: number | null; peak_gb: number | null; rss_peak_gb: number }
  > & { file?: string };
  router: {
    dev: { accuracy: number; confident_rate: number; confident_accuracy: number };
    test: { accuracy: number; confident_rate: number; confident_accuracy: number };
    latency_p90_ms: number;
    file: string;
  } | null;
  decisions: Decision[];
  calls: CallSummary[];
  examples: {
    case: string;
    said: string;
    understood: string;
    before: string;
    after: string;
    heard_reply: string;
  }[];
  template: { action: string; bank: Record<string, number>; spoken: string };
  customers: { number: string; name: string; born: string; cards: string[] }[];
  film: { video: string; poster: string; captions: string; megabytes: number } | null;
};

export type Turn = {
  turn: number;
  t: number; // when the agent had its answer, seconds from the start of the recording
  heard: string;
  understood: string;
  stt_ms: number | null;
  route: {
    skill: string;
    reason: string;
    intent: string | null;
    score: number | null;
    ms: number;
  };
  model: { output: string; first_token_ms: number | null; ms: number };
  action: { tool: string; arguments: Record<string, string | number> } | null;
  instead: string | null;
  bank: { ms: number; outcome: string } | null;
  spoken: string;
  reply_s?: number | null;
  stages_ms?: Record<string, number> | null;
};

export type Call = CallSummary & {
  call_id: string;
  recorded_at: string;
  llm: string;
  voice: string;
  greeting: string;
  caller_speaking: [number, number][];
  agent_speaking: [number, number][];
  turns: Turn[];
  envelope_hz: number;
  envelope: { caller: number[]; agent: number[] };
  audio: string;
};
