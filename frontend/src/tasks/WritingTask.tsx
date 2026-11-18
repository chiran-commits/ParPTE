import { useEffect, useRef, useState } from "react";
import { AudioBox } from "../components/AudioBox";
import { Button, cx, fmtTime } from "../components/ui";
import type { TaskProps } from "./types";

const countWords = (s: string) => (s.trim() ? s.trim().split(/\s+/).length : 0);

const LIMITS: Record<string, [number, number]> = {
  summarize_written_text: [5, 75],
  write_essay: [200, 300],
  summarize_spoken_text: [50, 70],
};

/** Summarize Written Text, Write Essay, Summarize Spoken Text and Write from Dictation. */
export function WritingTask({ q, meta, onSubmit, accent, mode }: TaskProps) {
  const [text, setText] = useState("");
  const [left, setLeft] = useState(meta.time ?? 0);
  const [audioDone, setAudioDone] = useState(!meta.audio);
  const sent = useRef(false);
  const words = countWords(text);
  const limit = LIMITS[q.task];
  const isWfd = q.task === "write_from_dictation";

  useEffect(() => {
    setText("");
    setLeft(meta.time ?? 0);
    setAudioDone(!meta.audio);
    sent.current = false;
  }, [q.id, meta.time, meta.audio]);

  useEffect(() => {
    if (!meta.time || !audioDone) return;
    if (left <= 0) {
      submit();
      return;
    }
    const t = setTimeout(() => setLeft((l) => l - 1), 1000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [left, audioDone, meta.time]);

  function submit() {
    if (sent.current) return;
    sent.current = true;
    onSubmit({ response: { text } });
  }

  return (
    <div className="space-y-5">
      {q.task === "summarize_written_text" && <div className="max-h-[360px] overflow-y-auto rounded-panel border border-line bg-white p-5 text-[17px] leading-[1.7]">{q.passage}</div>}
      {q.task === "write_essay" && <p className="rounded-panel border border-line bg-white p-5 text-[17px] leading-relaxed">{q.prompt}</p>}
      {meta.audio && <AudioBox q={q} accent={accent} delay={isWfd ? 3 : 5} onEnded={() => setAudioDone(true)} allowReplay={mode === "practice" && isWfd} />}

      {isWfd ? (
        <input
          className="w-full rounded-md border border-line bg-white px-4 py-3 text-[17px] focus:border-pine focus:outline-none"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && text.trim() && submit()}
          spellCheck={false}
          autoComplete="off"
          aria-label="Type the sentence you heard"
          placeholder="Type the sentence exactly as you heard it"
        />
      ) : (
        <div>
          <textarea
            className={cx(
              "w-full rounded-md border border-line bg-white p-4 text-[17px] leading-relaxed focus:border-pine focus:outline-none",
              q.task === "write_essay" ? "min-h-[380px]" : "min-h-[180px]",
            )}
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck={false}
            autoCorrect="off"
            autoCapitalize="off"
            aria-label="Your response"
            disabled={!audioDone}
          />
          <div className="mt-2 flex items-center justify-between text-sm">
            <span className={cx("tabular-nums", limit && (words < limit[0] || words > limit[1]) ? "text-coral" : "text-ink-soft")}>
              Word count: {words}
              {limit && <span className="text-ink-mute"> (target {limit[0]}–{limit[1]})</span>}
            </span>
            {meta.time && audioDone && <span className={cx("tabular-nums", left < 60 ? "font-semibold text-coral" : "text-ink-soft")}>Time left {fmtTime(left)}</span>}
          </div>
        </div>
      )}
      <div className="flex justify-end">
        <Button onClick={submit} disabled={!text.trim() || !audioDone}>
          {mode === "mock" ? "Save and next" : "Submit for scoring"}
        </Button>
      </div>
    </div>
  );
}
