import { useState } from "react";
import { Check } from "lucide-react";
import { PageTitle } from "../components/Layout";
import { Button, Notice, Panel, cx } from "../components/ui";
import { api } from "../lib/api";
import { useApp } from "../lib/app";

export default function Plans() {
  const { meta, user } = useApp();
  const [msg, setMsg] = useState<string | null>(null);
  if (!meta || !user) return null;

  async function choose(plan: string) {
    setMsg(null);
    try {
      const r = await api.post<{ url: string }>("/api/billing/checkout", { plan });
      window.location.href = r.url;
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  return (
    <div className="max-w-5xl">
      <PageTitle
        title="Plans"
        sub={user.role === "admin" ? "You're the developer, so every feature is unlocked for free on your account." : "Objective Reading and Listening questions are always free. Plans add AI scoring and mock tests."}
      />
      {msg && <div className="mb-5"><Notice tone="warn">{msg}</Notice></div>}
      <div className="grid gap-5 md:grid-cols-3">
        {Object.entries(meta.plans).map(([id, p]) => {
          const current = user.plan === id;
          return (
            <Panel key={id} className={cx("flex flex-col p-6", id === "pro" && "border-pine")}>
              <h2 className="text-xl font-semibold">{p.name}</h2>
              <p className="mt-2 font-display text-4xl font-bold">
                ${p.price_usd}
                {p.price_usd > 0 && <span className="text-base font-normal text-ink-mute"> / month</span>}
              </p>
              <ul className="mt-5 flex-1 space-y-2.5 text-[15px]">
                {p.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-pine" /> {f}
                  </li>
                ))}
              </ul>
              <Button className="mt-6" variant={current ? "secondary" : "primary"} disabled={current || id === "free"} onClick={() => choose(id)}>
                {current ? "Current plan" : id === "free" ? "Included" : `Upgrade to ${p.name}`}
              </Button>
            </Panel>
          );
        })}
      </div>
    </div>
  );
}
