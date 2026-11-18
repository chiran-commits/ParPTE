import { useEffect, useState } from "react";
import { PageTitle } from "../components/Layout";
import { Button, Notice, Panel, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useApp } from "../lib/app";
import type { User } from "../lib/types";

type AdminUser = User & { attempts: number };

const EXAMPLE = `{
  "title": "Campus parking",
  "text": "Parking permits for the new semester can be purchased online."
}`;

export default function Admin() {
  const { meta, user } = useApp();
  const [stats, setStats] = useState<any>(null);
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [search, setSearch] = useState("");
  const [task, setTask] = useState("write_from_dictation");
  const [json, setJson] = useState(EXAMPLE);
  const [msg, setMsg] = useState<{ tone: "info" | "error"; text: string } | null>(null);

  const load = () => {
    api.get("/api/admin/stats").then(setStats);
    api.get<AdminUser[]>(`/api/admin/users?q=${encodeURIComponent(search)}`).then(setUsers);
  };
  useEffect(load, [search]);

  if (user?.role !== "admin") return <Notice tone="error">Admins only.</Notice>;

  async function setPlan(id: number, plan: string) {
    await api.patch(`/api/admin/users/${id}`, { plan });
    load();
  }

  async function addQuestion() {
    setMsg(null);
    try {
      const data = JSON.parse(json);
      const q = await api.post<{ id: string }>("/api/admin/questions", { task, data });
      setMsg({ tone: "info", text: `Added question ${q.id}.` });
      load();
    } catch (e) {
      setMsg({ tone: "error", text: (e as Error).message });
    }
  }

  return (
    <div className="max-w-6xl">
      <PageTitle title="Admin" sub="Manage users, plans and the question bank." />
      {!stats ? (
        <Spinner />
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          <Panel className="p-5"><p className="font-display text-3xl font-bold">{stats.users}</p><p className="text-ink-mute">Users</p></Panel>
          <Panel className="p-5"><p className="font-display text-3xl font-bold">{stats.attempts}</p><p className="text-ink-mute">Answers scored</p></Panel>
          <Panel className="p-5"><p className="font-display text-3xl font-bold">{Object.values(stats.questions as Record<string, number>).reduce((a, b) => a + b, 0)}</p><p className="text-ink-mute">Questions</p></Panel>
        </div>
      )}

      <h2 className="mb-3 mt-10 text-xl font-semibold">Users</h2>
      <input className="mb-3 w-full max-w-sm rounded-md border border-line bg-white px-3.5 py-2 focus:border-pine focus:outline-none" placeholder="Search by email" value={search} onChange={(e) => setSearch(e.target.value)} />
      <Panel className="overflow-x-auto">
        <table className="w-full text-[15px]">
          <thead className="border-b border-line text-left text-ink-soft">
            <tr><th className="px-4 py-2.5">Email</th><th className="px-4">Role</th><th className="px-4">Answers</th><th className="px-4">Plan</th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {users?.map((u) => (
              <tr key={u.id}>
                <td className="px-4 py-2.5">{u.email}</td>
                <td className="px-4">{u.role}</td>
                <td className="px-4 tabular-nums">{u.attempts}</td>
                <td className="px-4">
                  <select value={u.plan} disabled={u.role === "admin"} onChange={(e) => setPlan(u.id, e.target.value)} className="rounded border border-line bg-white px-2 py-1">
                    {Object.keys(meta?.plans ?? {}).map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <h2 className="mb-3 mt-10 text-xl font-semibold">Add a question</h2>
      <Panel className="space-y-4 p-5">
        <p className="text-[15px] text-ink-soft">Paste the question as JSON, in the same format as the files in <code>backend/app/bank/data</code>. The id is generated if you leave it out.</p>
        <select value={task} onChange={(e) => setTask(e.target.value)} className="rounded-md border border-line bg-white px-3 py-2">
          {meta?.tasks.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.module})</option>)}
        </select>
        <textarea value={json} onChange={(e) => setJson(e.target.value)} className="min-h-[200px] w-full rounded-md border border-line bg-white p-3 font-[ui-monospace,monospace] text-[14px] focus:border-pine focus:outline-none" spellCheck={false} />
        <div className="flex items-center gap-4">
          <Button onClick={addQuestion}>Add question</Button>
          {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        </div>
      </Panel>
    </div>
  );
}
