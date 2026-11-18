import type { Question, Submission, TaskMeta } from "../lib/types";

export interface TaskProps {
  q: Question;
  meta: TaskMeta;
  accent: string;
  mode: "practice" | "mock";
  onSubmit: (s: Submission) => void;
}
