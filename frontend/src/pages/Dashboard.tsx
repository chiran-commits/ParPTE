import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PageTitle } from "../components/Layout";
import { Button, Notice, Panel, ScoreRuler, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { MODULE_LABEL, useApp } from "../lib/app";
import type { Module, Progress } from "../lib/types";

export default function Dashboard() {
  const { user, meta } = useApp();
  const [p, setP] = useState<Progress | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.get<Progress>("/api/progress").then(setP).catch((e) => setErr(e.message));
  }, []);

  if (err) return <Notice tone="error">{err}</Notice>;
  if (!p || !meta) return <Spinner label="Loading your progress" />;

  const target = p.target;
  const scored = meta.tasks.filter((t) => t.scored);
  const weakest = scored
    .filter((t) => p.tasks[t.id])
    .sort((a, b) => p.tasks[a.id].avg - p.tasks[b.id].avg)
    .slice(0, 4);
  const untried = scored.filter((t) => !p.tasks[t.id]).slice(0, 6);
  const daysToExam = user?.exam_date ? Math.ceil((new Date(user.exam_date).getTime() - Date.now()) / 86400000) : null;
  const first = user?.name?.split(" ")[0];

  return (
    <div className="max-w-6xl">
      <PageTitle
        title={first ? `Hi ${first}` : "Your dashboard"}
        sub={p.total_attempts ? "Your predicted score uses your latest answer to every question from the last 90 days." : "Answer a few questions in each section and your predicted score will appear here."}
        right={<Link to="/app/mock"><Button>Take a mock test</Button></Link>}
      />

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Panel className="p-6">
          <ScoreRuler value={p.predicted.overall} target={target} label="Predicted overall" />
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            {(meta.modules as Module[]).map((m) => (
              <Link key={m} to={`/app/practice/${m}`} className="rounded-md p-1 -m-1 hover:bg-paper">
                <ScoreRuler value={p.predicted.skills[m]} target={target} label={MODULE_LABEL[m]} compact />
              </Link>
            ))}
          </div>
          <p className="mt-6 text-[13px] text-ink-mute">
            {p.predicted.overall != null && Object.values(p.predicted.skills).some((v) => v == null) && "Overall is based only on the sections you've practised so far. "}
            The marigold marker is your target of {target}. Change it in Settings.
          </p>
        </Panel>

        <div className="grid content-start gap-6">
          <Panel className="grid grid-cols-3 divide-x divide-line">
            <Stat label="Day streak" value={p.streak} />
            <Stat label="Answers (90 days)" value={p.total_attempts} />
            {daysToExam != null && daysToExam >= 0 ? <Stat label="Days to exam" value={daysToExam} /> : <Stat label="AI scores today" value={p.quota.limit == null ? `${p.quota.used}` : `${p.quota.used}/${p.quota.limit}`} />}
          </Panel>
          <Panel className="p-5">
            <h2 className="text-lg font-semibold">Skills profile</h2>
            {Object.keys(p.predicted.profile).length ? (
              <ul className="mt-3 space-y-2.5">
                {Object.entries(p.predicted.profile)
                  .sort((a, b) => a[1] - b[1])
                  .slice(0, 7)
                  .map(([k, v]) => (
                    <li key={k} className="text-[15px]">
                      <div className="flex justify-between">
                        <span>{k}</span>
                        <span className="tabular-nums text-ink-soft">{v}%</span>
                      </div>
                      <div className="mt-1 h-1.5 rounded-full bg-paper-sunk">
                        <div className={`h-full rounded-full ${v >= 80 ? "bg-ok" : v >= 55 ? "bg-marigold" : "bg-coral"}`} style={{ width: `${v}%` }} />
                      </div>
                    </li>
                  ))}
              </ul>
            ) : (
              <p className="mt-2 text-[15px] text-ink-soft">Trait strengths and weaknesses show up after your first scored answers.</p>
            )}
          </Panel>
        </div>
      </div>

      {p.trend.length > 1 && (
        <Panel className="mt-6 p-6">
          <h2 className="text-lg font-semibold">Predicted overall, by week</h2>
          <Trend data={p.trend.map((t) => ({ label: t.week.slice(5), v: t.overall }))} target={target} />
        </Panel>
      )}

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <Panel className="p-5">
          <h2 className="text-lg font-semibold">Work on these next</h2>
          {weakest.length ? (
            <ul className="mt-3 divide-y divide-line">
              {weakest.map((t) => (
                <li key={t.id}>
                  <Link to={`/app/task/${t.id}`} className="flex items-center justify-between py-2.5 hover:text-pine">
                    <span>{t.name} <span className="text-ink-mute">· {MODULE_LABEL[t.module]}</span></span>
                    <span className="tabular-nums text-ink-soft">{p.tasks[t.id].avg}% avg</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-[15px] text-ink-soft">Your weakest question types will appear here.</p>
          )}
        </Panel>
        <Panel className="p-5">
          <h2 className="text-lg font-semibold">Not tried yet</h2>
          {untried.length ? (
            <ul className="mt-3 flex flex-wrap gap-2">
              {untried.map((t) => (
                <li key={t.id}>
                  <Link to={`/app/task/${t.id}`} className="inline-block rounded-md border border-line px-3 py-1.5 text-[15px] hover:border-pine hover:text-pine">
                    {t.name}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-[15px] text-ink-soft">You've practised every question type. Keep going.</p>
          )}
        </Panel>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="p-4 text-center">
      <p className="font-display text-3xl font-bold tabular-nums">{value}</p>
      <p className="text-[13px] text-ink-mute">{label}</p>
    </div>
  );
}

function Trend({ data, target }: { data: { label: string; v: number | null }[]; target: number }) {
  const W = 800, H = 200, L = 30, B = H - 24;
  const y = (v: number) => B - ((v - 10) / 80) * (B - 10);
  const x = (i: number) => L + ((W - L - 10) / Math.max(1, data.length - 1)) * i;
  const pts = data.map((d, i) => (d.v == null ? null : `${x(i)},${y(d.v)}`)).filter(Boolean);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full" role="img" aria-label="Weekly predicted overall score">
      {[30, 50, 70, 90].map((g) => (
        <g key={g}>
          <line x1={L} x2={W} y1={y(g)} y2={y(g)} stroke="#ECEEEA" />
          <text x={L - 6} y={y(g) + 4} fontSize="11" textAnchor="end" fill="#7A847F">{g}</text>
        </g>
      ))}
      <line x1={L} x2={W} y1={y(target)} y2={y(target)} stroke="#E9A20C" strokeDasharray="5 5" strokeWidth="1.5" />
      <polyline points={pts.join(" ")} fill="none" stroke="#0F5C4A" strokeWidth="2.5" />
      {data.map((d, i) => d.v != null && <circle key={i} cx={x(i)} cy={y(d.v)} r="3.5" fill="#0F5C4A" />)}
      {data.map((d, i) => (
        <text key={i} x={x(i)} y={H - 4} fontSize="11" textAnchor="middle" fill="#7A847F">{d.label}</text>
      ))}
    </svg>
  );
}
