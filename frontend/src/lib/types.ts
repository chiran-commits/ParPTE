export type Module = "speaking" | "writing" | "reading" | "listening";

export interface TaskMeta {
  id: string;
  name: string;
  abbr: string;
  module: Module;
  prep?: number;
  record?: number;
  time?: number;
  suggested?: number;
  audio: boolean;
  scored: boolean;
  new: boolean;
  count: number;
  skills: Module[];
}

export interface Plan {
  name: string;
  price_usd: number;
  daily_ai_scores: number | null;
  mocks: string[];
  features: string[];
}

export interface Meta {
  tasks: TaskMeta[];
  modules: Module[];
  plans: Record<string, Plan>;
  engines: Record<string, string | boolean>;
}

export interface User {
  id: number;
  email: string;
  name: string;
  role: "user" | "admin";
  plan: string;
  plan_expires_at: string | null;
  target_score: number;
  exam_date: string | null;
  accent: string;
}

export interface Option {
  id: string;
  text: string;
}

export interface Chart {
  type: "bar" | "line" | "pie" | "process";
  title: string;
  unit?: string;
  labels: string[];
  series: { name: string; values: number[] }[];
}

export type Segment = { t: string } | { blank: number };

export interface Question {
  id: string;
  task: string;
  title?: string;
  difficulty?: string;
  audio_url?: string;
  text?: string;
  prompt?: string;
  passage?: string;
  question?: string;
  situation?: string;
  audio_text?: string;
  audio_turns?: { speaker: string; text: string }[];
  chart?: Chart;
  options?: Option[];
  segments?: Segment[];
  blanks?: { options?: string[] }[];
  pool?: string[];
  paragraphs?: Option[];
  shown_words?: string[];
  stats?: { attempts: number; best: number | null; last: string | null } | null;
}

export interface Trait {
  name: string;
  score: number;
  max: number;
  raw?: number;
  note?: string;
}

export interface AlignedWord {
  ref: string | null;
  hyp: string | null;
  op: "ok" | "sub" | "del" | "ins";
}

export interface ScoreResult {
  attempt_id?: number;
  task: string;
  score: number;
  max: number;
  band: number | null;
  traits: Trait[];
  feedback: string[];
  detail: Record<string, any>;
  reveal: Record<string, any>;
}

export interface Progress {
  predicted: { overall: number | null; skills: Record<Module, number | null>; profile: Record<string, number>; items: number };
  tasks: Record<string, { attempts: number; avg: number }>;
  activity: Record<string, number>;
  streak: number;
  total_attempts: number;
  trend: ({ week: string; overall: number | null } & Partial<Record<Module, number | null>>)[];
  target: number;
  quota: { used: number; limit: number | null };
}

export interface MockSummary {
  id: number;
  kind: string;
  created_at: string;
  finished_at: string | null;
  count: number;
  result: (Progress["predicted"] & { breakdown: any[] }) | null;
  questions?: Question[];
  answered?: string[];
}

/** What a task component hands back when the user submits. */
export interface Submission {
  response: Record<string, unknown>;
  audio?: Blob | null;
}
