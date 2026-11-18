import { Link } from "react-router-dom";
import { BookOpen, Ear, Mic, PenLine } from "lucide-react";
import { Logo } from "../components/Layout";
import { Button, ScoreRuler, TraitBar } from "../components/ui";
import { useApp } from "../lib/app";

const SAMPLE: [string, "ok" | "del" | "sub"][] = [
  ["Coral", "ok"], ["reefs", "ok"], ["cover", "ok"], ["less", "ok"], ["than", "ok"], ["one", "ok"], ["percent", "ok"], ["of", "ok"], ["the", "ok"],
  ["ocean", "ok"], ["floor,", "ok"], ["yet", "ok"], ["they", "ok"], ["support", "ok"], ["about", "del"], ["a", "ok"], ["quarter", "ok"], ["of", "ok"],
  ["all", "ok"], ["marine", "sub"], ["species.", "ok"],
];

const MODULES = [
  { icon: Mic, name: "Speaking", tasks: "8 question types, including Summarize Group Discussion and Respond to a Situation", how: "Content, oral fluency and pronunciation, measured from your actual recording: pauses, pace, hesitations and how each word sounds." },
  { icon: PenLine, name: "Writing", tasks: "Summarize Written Text and Write Essay", how: "All seven essay traits on the 2025 scales, with form and content gates, spelling, grammar and vocabulary range." },
  { icon: BookOpen, name: "Reading", tasks: "5 question types", how: "Pearson's partial-credit rules, including negative marking on multiple-answer questions and pair scoring for Re-order Paragraphs." },
  { icon: Ear, name: "Listening", tasks: "8 question types", how: "Audio plays once like the real test. Write from Dictation is scored word by word, and Highlight Incorrect Words subtracts points for wrong clicks." },
];

export default function Landing() {
  const { user, meta } = useApp();
  return (
    <div className="bg-paper">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <Logo />
        <div className="flex items-center gap-2">
          {user ? (
            <Link to="/app"><Button>Open dashboard</Button></Link>
          ) : (
            <>
              <Link to="/login"><Button variant="ghost">Sign in</Button></Link>
              <Link to="/register"><Button>Start practising free</Button></Link>
            </>
          )}
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-10 lg:grid-cols-[1.05fr_1fr] lg:pt-16">
        <div>
          <h1 className="font-display text-[44px] font-bold leading-[1.05] tracking-tight sm:text-[58px]">
            Hear exactly where your PTE points go.
          </h1>
          <p className="mt-6 max-w-xl text-[19px] leading-relaxed text-ink-soft">
            Practise every PTE Academic question type and get scored on the same traits Pearson uses, down to the word you skipped and the pause that cost you fluency.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to={user ? "/app" : "/register"}><Button className="px-6 py-3 text-[16px]">Start practising free</Button></Link>
            <a href="#scoring"><Button variant="secondary" className="px-6 py-3 text-[16px]">How scoring works</Button></a>
          </div>
          <p className="mt-5 text-sm text-ink-mute">All 22 question types, including the August 2025 speaking additions. No card needed.</p>
        </div>

        <div className="rounded-panel border border-line bg-paper-raised p-6" aria-label="Example of a scored Read Aloud answer">
          <div className="flex items-baseline justify-between">
            <p className="font-display text-lg font-semibold">Read Aloud</p>
            <p className="font-display text-3xl font-bold tabular-nums">12.8<span className="text-lg text-ink-mute">/15</span></p>
          </div>
          <p className="mt-4 text-[17px] leading-[2]">
            {SAMPLE.map(([w, op], i) => (
              <span key={i}>
                {op === "ok" && w}
                {op === "del" && <span className="rounded bg-coral-tint px-1 text-coral line-through">{w}</span>}
                {op === "sub" && <span className="rounded bg-marigold-tint px-1">{w} <sup className="text-[11px] text-ink-soft">marin</sup></span>}{" "}
              </span>
            ))}
          </p>
          <div className="mt-5 space-y-3.5">
            <TraitBar name="Content" score={4.6} max={5} note="20 of 21 words correct" />
            <TraitBar name="Oral fluency" score={4} max={5} note="One hesitation after “support”" />
            <TraitBar name="Pronunciation" score={4} max={5} note="Practise: marine, species" />
          </div>
          <div className="mt-6 border-t border-line pt-5">
            <ScoreRuler value={76} target={79} label="Predicted speaking" />
          </div>
        </div>
      </section>

      <section className="border-y border-line bg-paper-raised">
        <div className="mx-auto max-w-6xl px-5 py-16">
          <h2 className="max-w-2xl text-[34px] font-bold leading-tight">Every section, scored the way the exam scores it</h2>
          <div className="mt-10 grid gap-x-10 gap-y-10 md:grid-cols-2">
            {MODULES.map(({ icon: Icon, name, tasks, how }) => (
              <div key={name} className="flex gap-4">
                <Icon className="mt-1 h-6 w-6 shrink-0 text-pine" aria-hidden />
                <div>
                  <h3 className="text-xl font-semibold">{name}</h3>
                  <p className="text-[15px] text-ink-mute">{tasks}</p>
                  <p className="mt-2 text-[16px] leading-relaxed text-ink-soft">{how}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="scoring" className="mx-auto max-w-6xl px-5 py-16">
        <div className="grid gap-10 lg:grid-cols-2">
          <div>
            <h2 className="text-[34px] font-bold leading-tight">How ParPTE scores you</h2>
            <p className="mt-4 text-[17px] leading-relaxed text-ink-soft">
              Pearson publishes the traits and point ranges for every question type, but not its scoring model. ParPTE follows the published rubric exactly, including the rule that a zero for content or form wipes out the whole answer, then uses speech and language models to judge each trait.
            </p>
            <p className="mt-4 text-[17px] leading-relaxed text-ink-soft">
              Your item scores feed a 10–90 estimate for each communicative skill, using the same integrated-skill links as the real test: Repeat Sentence counts toward listening, Write from Dictation toward writing.
            </p>
          </div>
          <dl className="grid content-start gap-5 text-[16px]">
            {[
              ["Speech recognition", "Whisper transcribes your answer with word timings, so every pause and filler is counted."],
              ["Pronunciation", "A phoneme model compares the sounds you produced with the sounds each word needs."],
              ["Writing traits", "A model trained on thousands of rated learner essays estimates cohesion, grammar and range."],
              ["Honest estimates", "Scores are predictions. Treat a 79 here as a strong signal, not a guarantee."],
            ].map(([k, v]) => (
              <div key={k} className="border-l-2 border-pine pl-4">
                <dt className="font-semibold">{k}</dt>
                <dd className="text-ink-soft">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {meta && (
        <section className="border-t border-line bg-paper-raised">
          <div className="mx-auto max-w-6xl px-5 py-16">
            <h2 className="text-[34px] font-bold">Plans</h2>
            <div className="mt-8 grid gap-5 md:grid-cols-3">
              {Object.entries(meta.plans).map(([id, p]) => (
                <div key={id} className={`rounded-panel border p-6 ${id === "pro" ? "border-pine" : "border-line"}`}>
                  <h3 className="text-xl font-semibold">{p.name}</h3>
                  <p className="mt-2 font-display text-4xl font-bold">
                    ${p.price_usd}
                    <span className="text-base font-normal text-ink-mute">{p.price_usd ? " / month" : ""}</span>
                  </p>
                  <ul className="mt-5 space-y-2 text-[15px] text-ink-soft">
                    {p.features.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap justify-between gap-4 px-5 py-8 text-sm text-ink-mute">
          <Logo />
          <p className="max-w-xl">
            ParPTE is an independent practice platform. It is not affiliated with or endorsed by Pearson. PTE and PTE Academic are trademarks of Pearson Education.
          </p>
        </div>
      </footer>
    </div>
  );
}
