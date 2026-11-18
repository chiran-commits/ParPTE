import { useEffect, useState, type DragEvent } from "react";
import { AudioBox } from "../components/AudioBox";
import { Button, cx } from "../components/ui";
import type { TaskProps } from "./types";

/** Reading & Writing FIB (dropdowns), Reading FIB (drag & drop or tap), Listening FIB (typed). */
export function FibTask({ q, meta, onSubmit, accent, mode }: TaskProps) {
  const n = q.blanks?.length ?? 0;
  const [vals, setVals] = useState<string[]>(Array(n).fill(""));
  const [held, setHeld] = useState<string | null>(null); // tap-to-place for touch screens
  const [ready, setReady] = useState(!meta.audio);

  useEffect(() => {
    setVals(Array(n).fill(""));
    setReady(!meta.audio);
    setHeld(null);
  }, [q.id, n, meta.audio]);

  const set = (i: number, v: string) => setVals((p) => p.map((x, j) => (j === i ? v : x)));
  const drag = q.task === "reading_fill_blanks";
  const used = new Set(vals.filter(Boolean));

  const place = (i: number, word: string) => {
    setVals((p) => p.map((x, j) => (j === i ? word : x === word ? "" : x)));
    setHeld(null);
  };

  const onDrop = (i: number) => (e: DragEvent) => {
    e.preventDefault();
    const w = e.dataTransfer.getData("text/plain");
    if (w) place(i, w);
  };

  return (
    <div className="space-y-5">
      {meta.audio && <AudioBox q={q} accent={accent} delay={5} onEnded={() => setReady(true)} allowReplay={mode === "practice"} />}
      <div className="rounded-panel border border-line bg-white p-5 text-[17px] leading-[2.4]">
        {q.segments?.map((s, k) =>
          "t" in s ? (
            <span key={k}>{s.t}</span>
          ) : q.task === "rw_fill_blanks" ? (
            <select
              key={k}
              aria-label={`Blank ${s.blank + 1}`}
              className="mx-1 rounded border border-line bg-paper px-2 py-1 text-[16px] focus:border-pine focus:outline-none"
              value={vals[s.blank]}
              onChange={(e) => set(s.blank, e.target.value)}
            >
              <option value="">—</option>
              {q.blanks?.[s.blank].options?.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </select>
          ) : drag ? (
            <span
              key={k}
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop(s.blank)}
              onClick={() => (held ? place(s.blank, held) : vals[s.blank] && set(s.blank, ""))}
              role="button"
              tabIndex={0}
              aria-label={`Blank ${s.blank + 1}${vals[s.blank] ? `: ${vals[s.blank]}` : ""}`}
              className={cx(
                "mx-1 inline-block min-w-[110px] rounded border-b-2 px-2 text-center align-baseline leading-8",
                vals[s.blank] ? "border-pine bg-pine-tint font-semibold" : "border-ink-mute bg-paper-sunk",
                held && "outline outline-1 outline-marigold",
              )}
            >
              {vals[s.blank] || " "}
            </span>
          ) : (
            <input
              key={k}
              aria-label={`Blank ${s.blank + 1}`}
              className="mx-1 w-32 rounded border border-line bg-paper px-2 py-0.5 text-[16px] focus:border-pine focus:outline-none"
              value={vals[s.blank]}
              onChange={(e) => set(s.blank, e.target.value)}
              spellCheck={false}
              autoComplete="off"
            />
          ),
        )}
      </div>
      {drag && (
        <div className="flex flex-wrap gap-2.5 rounded-panel border border-dashed border-line p-4">
          {q.pool?.map((w) => (
            <button
              key={w}
              draggable={!used.has(w)}
              onDragStart={(e) => e.dataTransfer.setData("text/plain", w)}
              onClick={() => setHeld(held === w ? null : w)}
              disabled={used.has(w)}
              className={cx(
                "rounded-md border px-3 py-1.5 text-[16px] font-semibold",
                used.has(w) ? "border-line text-ink-mute line-through" : held === w ? "border-marigold bg-marigold-tint" : "border-ink-mute bg-white hover:border-pine",
              )}
            >
              {w}
            </button>
          ))}
          <p className="w-full text-[13px] text-ink-mute">Drag a word into a gap, or tap a word and then tap a gap.</p>
        </div>
      )}
      <div className="flex justify-end">
        <Button disabled={!ready} onClick={() => onSubmit({ response: { blanks: Object.fromEntries(vals.map((v, i) => [String(i), v])) } })}>
          {mode === "mock" ? "Save and next" : "Check answers"}
        </Button>
      </div>
    </div>
  );
}
