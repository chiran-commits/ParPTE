import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PageTitle } from "../components/Layout";
import { Panel, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { MODULE_LABEL, useApp } from "../lib/app";
import type { Progress } from "../lib/types";

const BLURB: Record<string, string> = {
  speaking: "Recorded answers, scored on content, oral fluency and pronunciation. Use a headset and a quiet room for the most accurate results.",
  writing: "Timed writing tasks, scored on content, form, grammar, vocabulary, spelling and essay structure.",
  reading: "Objective questions scored with Pearson's partial-credit rules, including negative marking where it applies.",
  listening: "The audio plays once, as in the test. Use “Play again” in practice to check what you missed.",
};

const SKILL_NOTE = (skills: string[], module: string) => {
  const other = skills.filter((s) => s !== module);
  return other.length ? `Also counts toward ${other.map((s) => MODULE_LABEL[s].toLowerCase()).join(" and ")}` : "";
};

export default function ModulePage() {
  const { module = "speaking" } = useParams();
  const { meta } = useApp();
  const [p, setP] = useState<Progress | null>(null);
  useEffect(() => {
    api.get<Progress>("/api/progress").then(setP).catch(() => undefined);
  }, []);
  if (!meta) return <Spinner />;
  const tasks = meta.tasks.filter((t) => t.module === module);
  return (
    <div className="max-w-5xl">
      <PageTitle title={MODULE_LABEL[module] ?? module} sub={BLURB[module]} />
      <Panel className="divide-y divide-line">
        {tasks.map((t) => {
          const s = p?.tasks[t.id];
          return (
            <Link key={t.id} to={`/app/task/${t.id}`} className="grid grid-cols-[1fr_auto] items-center gap-4 px-5 py-4 hover:bg-paper">
              <div>
                <p className="text-[17px] font-semibold">
                  {t.name}
                  {t.new && <span className="ml-2 rounded bg-marigold-tint px-1.5 py-0.5 align-middle text-[12px] font-semibold text-ink">New in 2025</span>}
                  {!t.scored && <span className="ml-2 rounded bg-paper-sunk px-1.5 py-0.5 align-middle text-[12px] text-ink-soft">Not scored</span>}
                </p>
                <p className="text-[14px] text-ink-mute">
                  {t.count} question{t.count === 1 ? "" : "s"}
                  {t.prep != null && t.record != null && ` · ${t.prep ? `${t.prep} s to prepare, ` : ""}${t.record} s to speak`}
                  {t.time != null && ` · ${t.time / 60} minutes`}
                  {SKILL_NOTE(t.skills, t.module) && ` · ${SKILL_NOTE(t.skills, t.module)}`}
                </p>
              </div>
              <div className="text-right">
                {s ? (
                  <>
                    <p className="font-display text-xl font-bold tabular-nums">{s.avg}%</p>
                    <p className="text-[13px] text-ink-mute">{s.attempts} attempt{s.attempts === 1 ? "" : "s"}</p>
                  </>
                ) : (
                  <p className="text-[14px] font-semibold text-pine">Start</p>
                )}
              </div>
            </Link>
          );
        })}
      </Panel>
    </div>
  );
}
