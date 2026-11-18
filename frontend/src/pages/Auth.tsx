import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "../components/Layout";
import { Button, Notice } from "../components/ui";
import { useApp } from "../lib/app";

export default function Auth({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useApp();
  const nav = useNavigate();
  const loc = useLocation() as { state?: { from?: string } };
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, name);
      nav(loc.state?.from ?? "/app", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const field = "mt-1.5 w-full rounded-md border border-line bg-white px-3.5 py-2.5 text-[16px] focus:border-pine focus:outline-none";
  return (
    <div className="grid min-h-screen place-items-center px-5 py-10">
      <div className="w-full max-w-sm">
        <Logo />
        <h1 className="mt-8 text-[30px] font-bold">{mode === "login" ? "Sign in" : "Create your account"}</h1>
        <p className="mt-1 text-ink-soft">{mode === "login" ? "Pick up where you left off." : "Free forever for the basics. Upgrade any time."}</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          {mode === "register" && (
            <label className="block text-[15px] font-semibold">
              Name
              <input className={field} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
            </label>
          )}
          <label className="block text-[15px] font-semibold">
            Email
            <input className={field} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </label>
          <label className="block text-[15px] font-semibold">
            Password
            <input
              className={field}
              type="password"
              required
              minLength={mode === "register" ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
            {mode === "register" && <span className="mt-1 block text-[13px] font-normal text-ink-mute">At least 8 characters.</span>}
          </label>
          {error && <Notice tone="error">{error}</Notice>}
          <Button type="submit" disabled={busy} className="w-full py-3">
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>
        <p className="mt-6 text-[15px] text-ink-soft">
          {mode === "login" ? (
            <>No account yet? <Link to="/register" className="font-semibold text-pine hover:underline">Create one</Link></>
          ) : (
            <>Already registered? <Link to="/login" className="font-semibold text-pine hover:underline">Sign in</Link></>
          )}
        </p>
      </div>
    </div>
  );
}
