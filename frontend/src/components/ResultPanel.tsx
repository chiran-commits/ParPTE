import { Check, Sparkles, X } from "lucide-react";
import type { AlignedWord, Coach, ScoreResult } from "../lib/types";
import { Panel, ScoreRuler, TraitBar, cx } from "./ui";

export function ResultPanel({ r, audioUrl, target }: { r: ScoreResult; audioUrl?: string | null; target?: number }) {
  const d = r.detail ?? {};
  const rv = r.reveal ?? {};
  return (
    <Panel className="overflow-hidden">
      <div className="grid gap-6 border-b border-line p-6 md:grid-cols-[220px_1fr]">
        <div>
          <p className="text-sm text-ink-soft">Your score</p>
          <p className="font-display text-5xl font-bold tabular-nums">
            {Number.isInteger(r.score) ? r.score : r.score.toFixed(1)}
            <span className="text-2xl font-semibold text-ink-mute">/{r.max}</span>
          </p>
          {r.band != null && r.max > 0 && (
            <div className="mt-4">
              <ScoreRuler value={r.band} target={target} label="Item level" compact />
            </div>
          )}
        </div>
        <div className="space-y-4">
          {r.traits.length > 1 && r.traits.map((t) => <TraitBar key={t.name} {...t} />)}
          {r.traits.length <= 1 && <p className="text-[15px] text-ink-soft">Scored with Pearson's rules for this question type.</p>}
        </div>
      </div>

      <div className="space-y-6 p-6">
        {r.coach && r.coach.headline && <CoachBox c={r.coach} />}

        {d.fluency && Object.keys(d.fluency).length > 0 && <FluencyEvidence f={d.fluency} />}

        {r.feedback?.length > 0 && (
          <section>
            <h3 className="mb-2 font-display text-lg font-semibold">Everything we noticed</h3>
            <ul className="space-y-1.5 text-[15.5px]">
              {r.feedback.map((f, i) => (
                <li key={i} className="flex gap-2">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-marigold" />
                  {f}
                </li>
              ))}
            </ul>
          </section>
        )}

        {d.alignment && <Alignment words={d.alignment as AlignedWord[]} verified={d.content_engine === "acoustic"} browser={d.browser_transcript} />}

        {audioUrl && (
          <section>
            <h3 className="mb-2 font-display text-lg font-semibold">Your recording</h3>
            <audio controls src={audioUrl} className="w-full max-w-md" />
          </section>
        )}

        {d.transcript !== undefined && !d.alignment && (
          <section>
            <h3 className="mb-1 font-display text-lg font-semibold">What we heard</h3>
            <p className="text-[15.5px] italic text-ink-soft">{d.transcript || "No speech was recognised."}</p>
          </section>
        )}

        {d.pronunciation?.words?.length > 0 && (
          <section>
            <h3 className="mb-2 font-display text-lg font-semibold">Pronunciation by word</h3>
            <p className="flex flex-wrap gap-1.5 text-[15px]">
              {d.pronunciation.words.map((w: { word: string; level: string; sound?: string | null }, i: number) => (
                <span
                  key={i}
                  title={w.sound ? `Check the sound ${w.sound}` : undefined}
                  className={cx("rounded px-1.5 py-0.5", w.level === "good" ? "bg-ok-tint" : w.level === "weak" ? "bg-marigold-tint" : "bg-coral-tint font-semibold text-coral")}
                >
                  {w.word}
                </span>
              ))}
            </p>
            <p className="mt-2 flex flex-wrap gap-4 text-[13px] text-ink-mute">
              <span><span className="rounded bg-ok-tint px-1">word</span> clear</span>
              <span><span className="rounded bg-marigold-tint px-1">word</span> slightly unclear</span>
              <span><span className="rounded bg-coral-tint px-1 text-coral">word</span> mispronounced</span>
            </p>
          </section>
        )}

        {Array.isArray(d.key_points) && d.key_points.length > 0 && (
          <section>
            <h3 className="mb-2 font-display text-lg font-semibold">Key points</h3>
            <ul className="space-y-1.5 text-[15.5px]">
              {d.key_points.map((k: { label: string; covered: boolean }, i: number) => (
                <li key={i} className="flex gap-2">
                  {k.covered ? <Check className="mt-0.5 h-4 w-4 shrink-0 text-ok" /> : <X className="mt-0.5 h-4 w-4 shrink-0 text-coral" />}
                  <span className={k.covered ? "" : "text-ink-soft"}>{k.label}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {Array.isArray(d.functions) && (
          <section>
            <h3 className="mb-2 font-display text-lg font-semibold">What the situation needed</h3>
            <ul className="space-y-1.5 text-[15.5px]">
              {d.functions.map((f: { label: string; ok: boolean }, i: number) => (
                <li key={i} className="flex gap-2">
                  {f.ok ? <Check className="mt-0.5 h-4 w-4 text-ok" /> : <X className="mt-0.5 h-4 w-4 text-coral" />}
                  {f.label}
                </li>
              ))}
            </ul>
          </section>
        )}

        {(d.spelling?.length > 0 || d.grammar?.length > 0) && (
          <section className="grid gap-4 md:grid-cols-2">
            {d.spelling?.length > 0 && (
              <div>
                <h3 className="mb-2 font-display text-lg font-semibold">Spelling</h3>
                <ul className="space-y-1 text-[15px]">
                  {d.spelling.map((s: { word: string; suggestion: string }, i: number) => (
                    <li key={i}>
                      <s className="text-coral">{s.word}</s> {s.suggestion && <b className="text-ok">{s.suggestion}</b>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {d.grammar?.length > 0 && (
              <div>
                <h3 className="mb-2 font-display text-lg font-semibold">Grammar</h3>
                <ul className="space-y-1 text-[15px]">
                  {d.grammar.slice(0, 10).map((g: { message: string; text: string }, i: number) => (
                    <li key={i}>
                      <span className="text-ink-soft">“{g.text}”</span> — {g.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        {d.words && (
          <section>
            <h3 className="mb-2 font-display text-lg font-semibold">Dictation</h3>
            <p className="flex flex-wrap gap-1.5 text-[16px]">
              {d.words.map((w: { word: string; ok: boolean }, i: number) => (
                <span key={i} className={cx("rounded px-1.5", w.ok ? "bg-ok-tint" : "bg-coral-tint")}>
                  {w.word}
                </span>
              ))}
            </p>
          </section>
        )}

        {d.blanks && (
          <section>
            <h3 className="mb-2 font-display text-lg font-semibold">Answers</h3>
            <ol className="list-decimal space-y-1 pl-6 text-[15.5px]">
              {d.blanks.map((b: { given: string; correct: string; ok: boolean }, i: number) => (
                <li key={i}>
                  {b.ok ? <b className="text-ok">{b.correct}</b> : <><s className="text-coral">{b.given || "(blank)"}</s> → <b className="text-ok">{b.correct}</b></>}
                </li>
              ))}
            </ol>
          </section>
        )}

        {(Array.isArray(d.correct) || typeof d.correct === "string" || d.correct_order || rv.answer || rv.answers) && !d.blanks && !d.words && !d.alignment && (
          <p className="text-[15.5px]">
            Correct answer: <b className="text-ok">{[].concat(d.correct_order ?? d.correct ?? rv.answer ?? rv.answers).join(", ")}</b>
            {d.chosen !== undefined && <span className="text-ink-soft"> · You chose {[].concat(d.chosen ?? []).join(", ") || "nothing"}</span>}
          </p>
        )}

        <Reveal rv={rv} task={r.task} />
      </div>
    </Panel>
  );
}

export function CoachBox({ c }: { c: Coach }) {
  return (
    <section className="rounded-panel border border-pine/30 bg-pine-tint/60 p-5">
      <div className="flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-pine" aria-hidden />
        <h3 className="font-display text-lg font-semibold">Coach summary</h3>
        {c.source === "claude" && <span className="text-[12px] text-ink-mute">written by Claude</span>}
      </div>
      <p className="mt-2 text-[16px] font-semibold">{c.headline}</p>
      {c.priorities?.length > 0 && (
        <ol className="mt-3 space-y-3">
          {c.priorities.map((p, i) => (
            <li key={i} className="grid grid-cols-[24px_1fr] gap-2 text-[15.5px]">
              <span className="mt-0.5 grid h-6 w-6 place-items-center rounded-full bg-pine text-[13px] font-bold text-white">{i + 1}</span>
              <div>
                <p className="font-semibold">{p.title}</p>
                {p.why && <p className="text-ink-soft">{p.why}</p>}
                {p.drill && <p className="mt-0.5"><span className="font-semibold text-pine">Practice: </span>{p.drill}</p>}
              </div>
            </li>
          ))}
        </ol>
      )}
      {c.strengths?.length > 0 && <p className="mt-3 text-[14.5px] text-ink-soft"><span className="font-semibold text-ink">Strengths: </span>{c.strengths.join(", ")}</p>}
    </section>
  );
}

function FluencyEvidence({ f }: { f: Record<string, number> }) {
  const rows: [string, string, boolean][] = [
    ["Pace", `${f.syllables_per_sec} syllables/s`, f.syllables_per_sec >= 2.6 && f.syllables_per_sec <= 5.8],
    ["Phrase length", `${f.syllables_between_pauses} syllables between pauses`, f.syllables_between_pauses >= 5],
    ["Long pauses (1 s+)", String(f.long_pauses), f.long_pauses === 0],
    ["Fillers (um, uh)", String(f.fillers), f.fillers === 0],
    ["Mid-phrase hesitations", String(f.mid_phrase_hesitations), f.mid_phrase_hesitations === 0],
    ["Repetitions / restarts", String(f.repetitions_restarts), f.repetitions_restarts === 0],
  ];
  return (
    <section>
      <h3 className="mb-2 font-display text-lg font-semibold">Fluency evidence</h3>
      <dl className="grid gap-x-8 gap-y-1.5 text-[15px] sm:grid-cols-2">
        {rows.map(([k, v, ok]) => (
          <div key={k} className="flex items-center justify-between gap-3 border-b border-line py-1">
            <dt className="text-ink-soft">{k}</dt>
            <dd className={cx("tabular-nums font-semibold", ok ? "text-ok" : "text-coral")}>{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Alignment({ words, verified, browser }: { words: AlignedWord[]; verified?: boolean; browser?: string }) {
  return (
    <section>
      <h3 className="mb-1 font-display text-lg font-semibold">Word by word</h3>
      <p className="mb-2 text-[13.5px] text-ink-mute">
        {verified
          ? "Every word was checked against your recording, so browser recognition mistakes don't count against you."
          : "Based on your browser's transcript, which can mishear correct words."}
      </p>
      <p className="text-[17px] leading-[2.1]">
        {words.map((w, i) => (
          <span key={i}>
            {w.op === "ok" && <span>{w.ref}</span>}
            {w.op === "del" && <span className="rounded bg-coral-tint px-1 text-coral line-through" title="Missed">{w.ref}</span>}
            {w.op === "sub" && (
              <span className="rounded bg-marigold-tint px-1" title={`You said “${w.hyp}”`}>
                {w.ref} <sup className="text-[11px] text-ink-soft">{w.hyp}</sup>
              </span>
            )}
            {w.op === "ins" && <span className="rounded bg-paper-sunk px-1 text-[14px] italic text-ink-mute" title="Extra word">+{w.hyp}</span>}{" "}
          </span>
        ))}
      </p>
      <p className="mt-2 flex flex-wrap gap-4 text-[13px] text-ink-mute">
        <span><span className="rounded bg-coral-tint px-1 text-coral line-through">word</span> missed</span>
        <span><span className="rounded bg-marigold-tint px-1">word</span> said differently</span>
        <span><span className="rounded bg-paper-sunk px-1 italic">+word</span> extra</span>
      </p>
      {verified && browser && (
        <details className="mt-2 text-[13.5px] text-ink-mute">
          <summary className="cursor-pointer">What your browser thought it heard</summary>
          <p className="mt-1 italic">{browser}</p>
        </details>
      )}
    </section>
  );
}

function Reveal({ rv, task }: { rv: Record<string, any>; task: string }) {
  const text = rv.transcript ?? (["repeat_sentence", "write_from_dictation"].includes(task) ? rv.text : null);
  if (!text && !rv.turns) return null;
  return (
    <details className="rounded-md border border-line bg-paper px-4 py-3">
      <summary className="cursor-pointer font-semibold">Show the audio transcript</summary>
      {rv.turns ? (
        <div className="mt-3 space-y-2 text-[15.5px]">
          {rv.turns.map((t: { speaker: string; text: string }, i: number) => (
            <p key={i}>
              <b>{t.speaker}:</b> {t.text}
            </p>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-[15.5px] leading-relaxed">{text}</p>
      )}
    </details>
  );
}
