import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PageTitle } from "../components/Layout";
import { Button, Notice, Panel, ScoreRuler, Spinner } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { MODULE_LABEL, useApp } from "../lib/app";
import type { MockSummary, Module, Submission } from "../lib/types";
import { INSTRUCTIONS, TaskRunner } from "../tasks/TaskRunner";
import { CoachBox } from "../components/ResultPanel";

const KINDS = [
  { kind: "full", module: null, title: "Full mock test", body: "About two hours, every question type in exam order. Closest to the real thing." },
  { kind: "mini", module: null, title: "Mini mock test", body: "Around 35 minutes with a few questions of every type. Good for a weekly check-in." },
];

export function MockHome() {
  const nav = useNavigate();
  const { user, meta } = useApp();
  const [list, setList] = useState<MockSummary[] | null>(null);
  const [err, setErr] = useState<{ msg: string; upgrade?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<MockSummary[]>("/api/mock").then(setList).catch((e) => setErr({ msg: e.message }));
  }, []);

  async function start(kind: string, module: string | null) {
    setBusy(true);
    setErr(null);
    try {
      const m = await api.post<MockSummary>("/api/mock", { kind, module });
      nav(`/app/mock/${m.id}`);
    } catch (e) {
      setErr({ msg: (e as Error).message, upgrade: e instanceof ApiError && e.status === 402 });
      setBusy(false);
    }
  }

  const allowed = meta && user ? meta.plans[user.plan]?.mocks ?? [] : [];
  return (
    <div className="max-w-5xl">
      <PageTitle title="Mock tests" sub="Scores stay hidden until you finish, just like test day. Use headphones and set aside the full time." />
      {err && (
        <div className="mb-5">
          <Notice tone={err.upgrade ? "warn" : "error"}>
            {err.msg} {err.upgrade && <Link to="/app/plans" className="font-semibold underline">See plans</Link>}
          </Notice>
        </div>
      )}
      <div className="grid gap-5 md:grid-cols-2">
        {KINDS.map((k) => (
          <Panel key={k.kind} className="flex flex-col p-6">
            <h2 className="text-xl font-semibold">{k.title}</h2>
            <p className="mt-1 flex-1 text-[15.5px] text-ink-soft">{k.body}</p>
            <Button className="mt-5 self-start" disabled={busy} onClick={() => start(k.kind, k.module)}>
              {allowed.includes(k.kind) ? "Start" : "Start (Pro)"}
            </Button>
          </Panel>
        ))}
      </div>
      <h2 className="mb-3 mt-10 text-xl font-semibold">Practise one section</h2>
      <div className="flex flex-wrap gap-3">
        {(["speaking", "writing", "reading", "listening"] as Module[]).map((m) => (
          <Button key={m} variant="secondary" disabled={busy} onClick={() => start("mini", m)}>
            {MODULE_LABEL[m]} section
          </Button>
        ))}
      </div>

      <h2 className="mb-3 mt-10 text-xl font-semibold">Your results</h2>
      {!list && <Spinner />}
      {list?.length === 0 && <p className="text-ink-soft">No mock tests yet. Your results will be listed here.</p>}
      {list && list.length > 0 && (
        <Panel className="divide-y divide-line">
          {list.map((m) => (
            <Link key={m.id} to={m.finished_at ? `/app/mock/${m.id}/report` : `/app/mock/${m.id}`} className="flex items-center justify-between px-5 py-3.5 hover:bg-paper">
              <span>
                <b className="capitalize">{m.kind.replace(":", " · ")}</b>
                <span className="ml-2 text-[14px] text-ink-mute">{new Date(m.created_at).toLocaleDateString()}</span>
              </span>
              <span className="font-display text-xl font-bold tabular-nums">{m.finished_at ? m.result?.overall ?? "—" : <span className="text-[15px] font-semibold text-pine">Resume</span>}</span>
            </Link>
          ))}
        </Panel>
      )}
    </div>
  );
}

export function MockRun() {
  const { id } = useParams();
  const nav = useNavigate();
  const { task, user } = useApp();
  const [m, setM] = useState<MockSummary | null>(null);
  const [i, setI] = useState(0);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<MockSummary>(`/api/mock/${id}`)
      .then((d) => {
        if (d.finished_at) return nav(`/app/mock/${id}/report`, { replace: true });
        setM(d);
        const firstOpen = d.questions!.findIndex((q) => !d.answered?.includes(q.id));
        setI(firstOpen < 0 ? d.questions!.length : firstOpen);
      })
      .catch((e) => setErr(e.message));
  }, [id, nav]);

  const qs = m?.questions ?? [];
  const q = qs[i];
  const meta = q ? task(q.task) : undefined;
  const section = useMemo(() => (meta ? MODULE_LABEL[meta.module] : ""), [meta]);

  async function finish() {
    setSaving(true);
    try {
      await api.post(`/api/mock/${id}/finish`);
      nav(`/app/mock/${id}/report`);
    } catch (e) {
      setErr((e as Error).message);
      setSaving(false);
    }
  }

  async function onSubmit(s: Submission) {
    if (!q) return;
    setSaving(true);
    setErr(null);
    try {
      await api.submit(`/api/mock/${id}/answer/${q.id}`, s.response, s.audio);
      setI((x) => x + 1);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (err && !m) return <Notice tone="error">{err}</Notice>;
  if (!m) return <Spinner label="Preparing your test" />;

  if (!q)
    return (
      <div className="max-w-xl">
        <PageTitle title="All questions answered" sub="Finish the test to see your scores." />
        <Button onClick={finish} disabled={saving}>{saving ? "Calculating…" : "Finish and see results"}</Button>
      </div>
    );

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
        <div>
          <p className="text-[14px] text-ink-mute">{section} · Question {i + 1} of {qs.length}</p>
          <h1 className="font-display text-2xl font-bold">{meta?.name}</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => setI((x) => x + 1)} disabled={saving}>Skip</Button>
          <Button variant="secondary" onClick={finish} disabled={saving}>End test</Button>
        </div>
      </div>
      <div className="mb-5 h-1 rounded-full bg-paper-sunk">
        <div className="h-full rounded-full bg-pine" style={{ width: `${(i / qs.length) * 100}%` }} />
      </div>
      <p className="mb-5 text-[16px] text-ink-soft">{INSTRUCTIONS[q.task]}</p>
      {meta && <TaskRunner key={q.id} q={q} meta={meta} accent={user?.accent ?? "en-GB"} mode="mock" onSubmit={onSubmit} />}
      {saving && <div className="mt-4"><Spinner label="Saving your answer" /></div>}
      {err && <div className="mt-4"><Notice tone="error">{err}</Notice></div>}
    </div>
  );
}

export function MockReport() {
  const { id } = useParams();
  const { user, meta } = useApp();
  const [m, setM] = useState<MockSummary | null>(null);
  useEffect(() => {
    api.get<MockSummary>(`/api/mock/${id}`).then(setM);
  }, [id]);
  if (!m || !meta) return <Spinner />;
  const r = m.result;
  if (!r) return <Notice>This test hasn't been finished yet. <Link to={`/app/mock/${id}`} className="font-semibold underline">Resume it</Link></Notice>;

  const byTask: Record<string, { s: number; mx: number; n: number }> = {};
  for (const b of r.breakdown) {
    const t = (byTask[b.task] ??= { s: 0, mx: 0, n: 0 });
    t.s += b.score;
    t.mx += b.max;
    t.n += 1;
  }
  const target = user?.target_score ?? 79;
  return (
    <div className="max-w-5xl">
      <PageTitle title="Mock test results" sub={`${m.kind.replace(":", " · ")} · ${new Date(m.created_at).toLocaleString()}`} right={<Link to="/app/mock"><Button variant="secondary">All mock tests</Button></Link>} />
      <Panel className="p-6">
        <ScoreRuler value={r.overall} target={target} label="Overall" />
        <div className="mt-8 grid gap-6 sm:grid-cols-2">
          {(meta.modules as Module[]).map((mod) => (
            <ScoreRuler key={mod} value={r.skills[mod]} target={target} label={MODULE_LABEL[mod]} compact />
          ))}
        </div>
      </Panel>
      {r.coach && <div className="mt-6"><CoachBox c={r.coach} /></div>}
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <Panel className="p-5">
          <h2 className="mb-3 text-lg font-semibold">By question type</h2>
          <table className="w-full text-[15px]">
            <tbody className="divide-y divide-line">
              {Object.entries(byTask).map(([t, v]) => (
                <tr key={t}>
                  <td className="py-2">{meta.tasks.find((x) => x.id === t)?.name}</td>
                  <td className="py-2 text-right tabular-nums text-ink-soft">{v.mx ? Math.round((v.s / v.mx) * 100) : 0}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel className="p-5">
          <h2 className="mb-3 text-lg font-semibold">Skills profile</h2>
          <ul className="space-y-2 text-[15px]">
            {Object.entries(r.profile).sort((a, b) => a[1] - b[1]).map(([k, v]) => (
              <li key={k} className="flex justify-between">
                <span>{k}</span>
                <span className="tabular-nums text-ink-soft">{v}%</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
