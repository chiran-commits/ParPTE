import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, GripVertical } from "lucide-react";
import { AudioBox } from "../components/AudioBox";
import { Button, cx } from "../components/ui";
import type { Option } from "../lib/types";
import type { TaskProps } from "./types";

/** Re-order Paragraphs: source list → answer list, with drag, keyboard arrows and tap. */
export function ReorderTask({ q, onSubmit, mode }: TaskProps) {
  const [source, setSource] = useState<Option[]>(q.paragraphs ?? []);
  const [target, setTarget] = useState<Option[]>([]);
  const [dragId, setDragId] = useState<string | null>(null);

  useEffect(() => {
    setSource(q.paragraphs ?? []);
    setTarget([]);
  }, [q.id, q.paragraphs]);

  const moveToTarget = (p: Option) => {
    setSource((s) => s.filter((x) => x.id !== p.id));
    setTarget((t) => [...t, p]);
  };
  const moveToSource = (p: Option) => {
    setTarget((t) => t.filter((x) => x.id !== p.id));
    setSource((s) => [...s, p]);
  };
  const shift = (i: number, d: number) =>
    setTarget((t) => {
      const j = i + d;
      if (j < 0 || j >= t.length) return t;
      const c = [...t];
      [c[i], c[j]] = [c[j], c[i]];
      return c;
    });
  const dropOn = (i: number) => {
    if (!dragId) return;
    const fromSource = source.find((s) => s.id === dragId);
    if (fromSource) {
      setSource((s) => s.filter((x) => x.id !== dragId));
      setTarget((t) => [...t.slice(0, i), fromSource, ...t.slice(i)]);
    } else {
      setTarget((t) => {
        const from = t.findIndex((x) => x.id === dragId);
        const c = [...t];
        const [it] = c.splice(from, 1);
        c.splice(i > from ? i - 1 : i, 0, it);
        return c;
      });
    }
    setDragId(null);
  };

  const Card = ({ p, side, i }: { p: Option; side: "s" | "t"; i: number }) => (
    <li
      draggable
      onDragStart={() => setDragId(p.id)}
      onDragOver={(e) => side === "t" && e.preventDefault()}
      onDrop={() => side === "t" && dropOn(i)}
      className="group flex items-start gap-2 rounded-md border border-line bg-white p-3 text-[15.5px] leading-snug"
    >
      <GripVertical className="mt-0.5 h-4 w-4 shrink-0 cursor-grab text-ink-mute" aria-hidden />
      <button className="flex-1 text-left" onClick={() => (side === "s" ? moveToTarget(p) : moveToSource(p))} aria-label={side === "s" ? "Add to answer" : "Remove from answer"}>
        {p.text}
      </button>
      {side === "t" && (
        <span className="flex flex-col">
          <button onClick={() => shift(i, -1)} aria-label="Move up" className="text-ink-mute hover:text-pine">
            <ArrowUp className="h-4 w-4" />
          </button>
          <button onClick={() => shift(i, 1)} aria-label="Move down" className="text-ink-mute hover:text-pine">
            <ArrowDown className="h-4 w-4" />
          </button>
        </span>
      )}
    </li>
  );

  return (
    <div className="space-y-5">
      <div className="grid gap-5 md:grid-cols-2">
        <section>
          <h3 className="mb-2 font-semibold text-ink-soft">Source</h3>
          <ul className="min-h-[200px] space-y-2.5 rounded-panel bg-paper-sunk p-3">
            {source.map((p, i) => (
              <Card key={p.id} p={p} side="s" i={i} />
            ))}
          </ul>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-ink-soft">Your order</h3>
          <ul className="min-h-[200px] space-y-2.5 rounded-panel border-2 border-dashed border-line p-3" onDragOver={(e) => e.preventDefault()} onDrop={() => dropOn(target.length)}>
            {target.map((p, i) => (
              <Card key={p.id} p={p} side="t" i={i} />
            ))}
            {!target.length && <li className="p-6 text-center text-sm text-ink-mute">Tap or drag paragraphs here in the order they should appear.</li>}
          </ul>
        </section>
      </div>
      <div className="flex justify-end">
        <Button disabled={mode === "practice" && source.length > 0} onClick={() => onSubmit({ response: { order: target.map((t) => t.id) } })}>
          {mode === "mock" ? "Save and next" : "Check order"}
        </Button>
      </div>
    </div>
  );
}

/** Highlight Incorrect Words: click words in the transcript that differ from the recording. */
export function HighlightTask({ q, meta, onSubmit, accent, mode }: TaskProps) {
  const [sel, setSel] = useState<number[]>([]);
  const [ready, setReady] = useState(!meta.audio);
  useEffect(() => {
    setSel([]);
    setReady(false);
  }, [q.id]);
  const toggle = (i: number) => setSel((s) => (s.includes(i) ? s.filter((x) => x !== i) : [...s, i]));
  return (
    <div className="space-y-5">
      <AudioBox q={q} accent={accent} delay={7} onEnded={() => setReady(true)} allowReplay={mode === "practice"} />
      <p className="text-sm text-ink-mute">Click every word that is different from what the speaker says. Each wrong click costs a point.</p>
      <p className="rounded-panel border border-line bg-white p-5 text-[18px] leading-[2]">
        {q.shown_words?.map((w, i) => (
          <span key={i}>
            <button
              onClick={() => toggle(i)}
              className={cx("rounded px-0.5", sel.includes(i) ? "bg-marigold text-ink" : "hover:bg-paper-sunk")}
              aria-pressed={sel.includes(i)}
            >
              {w}
            </button>{" "}
          </span>
        ))}
      </p>
      <div className="flex justify-end">
        <Button disabled={!ready} onClick={() => onSubmit({ response: { selected: sel } })}>
          {mode === "mock" ? "Save and next" : "Check answers"}
        </Button>
      </div>
    </div>
  );
}
