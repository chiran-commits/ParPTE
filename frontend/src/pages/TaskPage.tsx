import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { ResultPanel } from "../components/ResultPanel";
import { Button, Notice, Spinner, cx } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { MODULE_LABEL, useApp } from "../lib/app";
import type { Question, ScoreResult, Submission } from "../lib/types";
import { INSTRUCTIONS, TaskRunner } from "../tasks/TaskRunner";

export default function TaskPage() {
  const { task = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const { task: getTask, user } = useApp();
  const meta = getTask(task);
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [result, setResult] = useState<ScoreResult | null>(null);
  const [scoring, setScoring] = useState(false);
  const [error, setError] = useState<{ msg: string; upgrade?: boolean } | null>(null);
  const [nonce, setNonce] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  const load = () => api.get<Question[]>(`/api/questions?task=${task}`).then(setQuestions).catch((e) => setError({ msg: e.message }));
  useEffect(() => {
    setQuestions(null);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task]);

  const idx = useMemo(() => {
    if (!questions?.length) return 0;
    const i = questions.findIndex((q) => q.id === sp.get("q"));
    return i < 0 ? 0 : i;
  }, [questions, sp]);
  const q = questions?.[idx];

  useEffect(() => {
    setResult(null);
    setError(null);
    setAudioUrl((u) => (u && URL.revokeObjectURL(u), null));
  }, [q?.id, nonce]);

  async function onSubmit(s: Submission) {
    if (!q) return;
    setScoring(true);
    setError(null);
    if (s.audio) setAudioUrl(URL.createObjectURL(s.audio));
    try {
      const r = await api.submit<ScoreResult>(`/api/score/${q.id}`, s.response, s.audio);
      setResult(r);
      load();
    } catch (e) {
      setError({ msg: (e as Error).message, upgrade: e instanceof ApiError && e.status === 402 });
    } finally {
      setScoring(false);
    }
  }

  const go = (i: number) => questions && setSp({ q: questions[(i + questions.length) % questions.length].id });

  if (!meta) return <Notice tone="error">Unknown question type.</Notice>;

  return (
    <div className="max-w-6xl">
      <Link to={`/app/practice/${meta.module}`} className="mb-4 inline-flex items-center gap-1 text-[15px] text-ink-soft hover:text-pine">
        <ChevronLeft className="h-4 w-4" /> {MODULE_LABEL[meta.module]}
      </Link>
      <div className="grid gap-8 lg:grid-cols-[1fr_250px]">
        <div className="min-w-0">
          <div className="mb-5">
            <h1 className="font-display text-[30px] font-bold leading-tight">{meta.name}</h1>
            <p className="mt-1 text-[16px] text-ink-soft">{INSTRUCTIONS[task]}</p>
          </div>
          {!questions && <Spinner label="Loading questions" />}
          {q && (
            <>
              <div className="mb-4 flex items-center justify-between text-[14px] text-ink-mute">
                <span>
                  Question {idx + 1} of {questions!.length}
                  {q.title && <> · {q.title}</>}
                  {q.difficulty && <> · {q.difficulty}</>}
                </span>
              </div>
              <TaskRunner key={`${q.id}-${nonce}`} q={q} meta={meta} accent={user?.accent ?? "en-GB"} mode="practice" onSubmit={onSubmit} />
            </>
          )}
          <div className="mt-6 space-y-4" aria-live="polite">
            {scoring && <Spinner label="Scoring your answer" />}
            {error && (
              <Notice tone={error.upgrade ? "warn" : "error"}>
                {error.msg} {error.upgrade && <Link to="/app/plans" className="font-semibold underline">See plans</Link>}
              </Notice>
            )}
            {result && <ResultPanel r={result} audioUrl={audioUrl} target={user?.target_score} />}
            {(result || error) && (
              <div className="flex flex-wrap gap-3">
                <Button variant="secondary" onClick={() => setNonce((n) => n + 1)}>Try again</Button>
                <Button onClick={() => go(idx + 1)}>Next question</Button>
              </div>
            )}
          </div>
        </div>

        <aside className="lg:sticky lg:top-8 lg:self-start">
          <h2 className="mb-2 text-[15px] font-semibold text-ink-soft">Questions</h2>
          <ol className="max-h-[70vh] space-y-1 overflow-y-auto">
            {questions?.map((x, i) => (
              <li key={x.id}>
                <button
                  onClick={() => go(i)}
                  className={cx("flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-[15px]", i === idx ? "bg-pine text-white" : "hover:bg-paper-sunk")}
                >
                  <span className="truncate">{i + 1}. {x.title ?? x.id.toUpperCase()}</span>
                  {x.stats?.best != null && (
                    <span className={cx("shrink-0 text-[13px] tabular-nums", i === idx ? "text-white/80" : "text-ink-mute")}>{Math.round(x.stats.best * 100)}%</span>
                  )}
                </button>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </div>
  );
}
