import { useState, type FormEvent } from "react";
import { PageTitle } from "../components/Layout";
import { Button, Notice, Panel } from "../components/ui";
import { api } from "../lib/api";
import { useApp } from "../lib/app";
import { speak } from "../lib/audio";
import type { User } from "../lib/types";

const ACCENTS = [
  ["en-GB", "British"],
  ["en-US", "American"],
  ["en-AU", "Australian"],
  ["en-IN", "Indian"],
];

export default function Settings() {
  const { user, setUser, meta } = useApp();
  const [name, setName] = useState(user?.name ?? "");
  const [target, setTarget] = useState(user?.target_score ?? 79);
  const [exam, setExam] = useState(user?.exam_date ?? "");
  const [accent, setAccent] = useState(user?.accent ?? "en-GB");
  const [msg, setMsg] = useState<{ tone: "info" | "error"; text: string } | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      const u = await api.patch<User>("/api/auth/me", { name, target_score: target, exam_date: exam || null, accent });
      setUser(u);
      setMsg({ tone: "info", text: "Settings saved." });
    } catch (err) {
      setMsg({ tone: "error", text: (err as Error).message });
    }
  }

  const field = "mt-1.5 w-full rounded-md border border-line bg-white px-3.5 py-2.5 text-[16px] focus:border-pine focus:outline-none";
  const e = meta?.engines ?? {};
  return (
    <div className="max-w-3xl">
      <PageTitle title="Settings" />
      <Panel className="p-6">
        <form onSubmit={save} className="grid gap-5 sm:grid-cols-2">
          <label className="block font-semibold">
            Name
            <input className={field} value={name} onChange={(x) => setName(x.target.value)} />
          </label>
          <label className="block font-semibold">
            Target score
            <select className={field} value={target} onChange={(x) => setTarget(Number(x.target.value))}>
              {[50, 58, 65, 73, 79, 85, 90].map((v) => (
                <option key={v} value={v}>{v}{v === 65 ? " (Proficient)" : v === 79 ? " (Superior)" : ""}</option>
              ))}
            </select>
          </label>
          <label className="block font-semibold">
            Exam date
            <input type="date" className={field} value={exam} onChange={(x) => setExam(x.target.value)} />
          </label>
          <label className="block font-semibold">
            Audio accent
            <div className="flex gap-2">
              <select className={field} value={accent} onChange={(x) => setAccent(x.target.value)}>
                {ACCENTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <Button type="button" variant="secondary" className="mt-1.5" onClick={() => speak("This is how practice audio will sound.", { accent })}>Test</Button>
            </div>
          </label>
          <div className="sm:col-span-2 flex items-center gap-4">
            <Button type="submit">Save settings</Button>
            {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
          </div>
        </form>
      </Panel>

      <Panel className="mt-6 p-6">
        <h2 className="text-lg font-semibold">Scoring engine</h2>
        <p className="mt-1 text-[15px] text-ink-soft">What the server is using to score your answers right now.</p>
        <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-[15px]">
          <dt className="text-ink-soft">Speech recognition</dt>
          <dd>{e.asr === "whisper" ? "Whisper (server)" : "Browser speech recognition (Chrome or Edge)"}</dd>
          <dt className="text-ink-soft">Pronunciation</dt>
          <dd>{e.pronunciation === "phoneme" ? "Phoneme model" : "Recognition-confidence estimate"}</dd>
          <dt className="text-ink-soft">Content similarity</dt>
          <dd>{e.similarity === "embeddings" ? "Sentence embeddings" : "Keyword overlap"}</dd>
          <dt className="text-ink-soft">Trained models</dt>
          <dd>{[e.essay_traits && "essay traits", e.speaking_traits && "speaking traits", e.speaking_ssl && "speaking audio model"].filter(Boolean).join(", ") || "None loaded yet"}</dd>
        </dl>
      </Panel>
    </div>
  );
}
