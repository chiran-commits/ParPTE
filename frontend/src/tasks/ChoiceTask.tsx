import { useEffect, useState } from "react";
import { AudioBox } from "../components/AudioBox";
import { Button, cx } from "../components/ui";
import type { TaskProps } from "./types";

const MULTI = new Set(["mcq_multiple_reading", "mcq_multiple_listening"]);
const PROMPT: Record<string, string> = {
  highlight_correct_summary: "Select the paragraph that best summarizes the recording.",
  select_missing_word: "Select the option that best completes the recording.",
};

/** MCQ single/multiple (reading & listening), Highlight Correct Summary, Select Missing Word. */
export function ChoiceTask({ q, meta, onSubmit, accent, mode }: TaskProps) {
  const multi = MULTI.has(q.task);
  const [picked, setPicked] = useState<string[]>([]);
  const [ready, setReady] = useState(!meta.audio);

  useEffect(() => {
    setPicked([]);
    setReady(!meta.audio);
  }, [q.id, meta.audio]);

  const toggle = (id: string) => setPicked((p) => (multi ? (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]) : [id]));

  return (
    <div className="space-y-5">
      {meta.audio && <AudioBox q={q} accent={accent} delay={5} onEnded={() => setReady(true)} cutAtEnd={q.task === "select_missing_word"} allowReplay={mode === "practice"} />}
      <div className={cx("grid gap-6", q.passage && "lg:grid-cols-2")}>
        {q.passage && <div className="rounded-panel border border-line bg-white p-5 text-[17px] leading-[1.7]">{q.passage}</div>}
        <fieldset>
          <legend className="mb-3 text-[17px] font-semibold">{q.question ?? PROMPT[q.task]}</legend>
          {multi && <p className="mb-3 text-sm text-ink-mute">More than one answer is correct. Wrong choices cost a point, so only select options you're sure about.</p>}
          <div className="space-y-2.5">
            {q.options?.map((o) => {
              const on = picked.includes(o.id);
              return (
                <label
                  key={o.id}
                  className={cx(
                    "flex cursor-pointer gap-3 rounded-md border px-4 py-3 text-[16px] leading-snug transition-colors",
                    on ? "border-pine bg-pine-tint" : "border-line bg-white hover:border-ink-mute",
                  )}
                >
                  <input type={multi ? "checkbox" : "radio"} name={q.id} className="mt-1 accent-[#0F5C4A]" checked={on} onChange={() => toggle(o.id)} />
                  <span>
                    <b className="mr-1.5 text-ink-soft">{o.id}.</b>
                    {o.text}
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>
      </div>
      <div className="flex justify-end">
        <Button disabled={!ready || (!picked.length && mode === "practice")} onClick={() => onSubmit({ response: multi ? { answers: picked } : { answer: picked[0] ?? null } })}>
          {mode === "mock" ? "Save and next" : "Check answer"}
        </Button>
      </div>
    </div>
  );
}
