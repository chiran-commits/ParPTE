import { useState, type ReactNode } from "react";
import { NavLink, Link } from "react-router-dom";
import { BookOpen, ClipboardList, Ear, Gauge, LogOut, Menu, Mic, PenLine, Settings, Shield, Sparkles, X } from "lucide-react";
import { useApp } from "../lib/app";
import { cx } from "./ui";

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2.5" aria-label="ParPTE home">
      <img src="/favicon.svg" alt="" className="h-8 w-8" />
      <span className={cx("font-display text-[22px] font-bold tracking-tight", light ? "text-white" : "text-ink")}>
        Par<span className="font-semibold">PTE</span>
      </span>
    </Link>
  );
}

const NAV = [
  { to: "/app", label: "Dashboard", icon: Gauge, end: true },
  { to: "/app/practice/speaking", label: "Speaking", icon: Mic },
  { to: "/app/practice/writing", label: "Writing", icon: PenLine },
  { to: "/app/practice/reading", label: "Reading", icon: BookOpen },
  { to: "/app/practice/listening", label: "Listening", icon: Ear },
  { to: "/app/mock", label: "Mock tests", icon: ClipboardList },
];

export function AppLayout({ children }: { children: ReactNode }) {
  const { user, logout, meta } = useApp();
  const [open, setOpen] = useState(false);
  const plan = user ? meta?.plans[user.plan]?.name ?? user.plan : "";

  const nav = (
    <nav className="flex flex-col gap-1" onClick={() => setOpen(false)}>
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            cx("flex items-center gap-3 rounded-md px-3 py-2.5 text-[15.5px] font-semibold", isActive ? "bg-pine text-white" : "text-ink-soft hover:bg-paper-sunk hover:text-ink")
          }
        >
          <Icon className="h-[18px] w-[18px]" aria-hidden />
          {label}
        </NavLink>
      ))}
      <div className="my-3 h-px bg-line" />
      <NavLink to="/app/plans" className={({ isActive }) => cx("flex items-center gap-3 rounded-md px-3 py-2.5 text-[15px]", isActive ? "bg-paper-sunk text-ink" : "text-ink-soft hover:text-ink")}>
        <Sparkles className="h-[18px] w-[18px]" aria-hidden /> Plans
      </NavLink>
      <NavLink to="/app/settings" className={({ isActive }) => cx("flex items-center gap-3 rounded-md px-3 py-2.5 text-[15px]", isActive ? "bg-paper-sunk text-ink" : "text-ink-soft hover:text-ink")}>
        <Settings className="h-[18px] w-[18px]" aria-hidden /> Settings
      </NavLink>
      {user?.role === "admin" && (
        <NavLink to="/app/admin" className={({ isActive }) => cx("flex items-center gap-3 rounded-md px-3 py-2.5 text-[15px]", isActive ? "bg-paper-sunk text-ink" : "text-ink-soft hover:text-ink")}>
          <Shield className="h-[18px] w-[18px]" aria-hidden /> Admin
        </NavLink>
      )}
    </nav>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      <aside className="hidden border-r border-line bg-paper-raised p-5 lg:flex lg:flex-col">
        <Logo />
        <div className="mt-8 flex-1">{nav}</div>
        <div className="border-t border-line pt-4 text-sm">
          <p className="truncate font-semibold">{user?.name}</p>
          <p className="text-ink-mute">{user?.role === "admin" ? "Developer · full access" : `${plan} plan`}</p>
          <button onClick={logout} className="mt-3 flex items-center gap-2 text-ink-soft hover:text-coral">
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </aside>

      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-paper-raised px-4 py-3 lg:hidden">
        <Logo />
        <button onClick={() => setOpen(!open)} aria-label="Menu" className="p-2">
          {open ? <X /> : <Menu />}
        </button>
      </header>
      {open && <div className="border-b border-line bg-paper-raised p-4 lg:hidden">{nav}</div>}

      <main className="min-w-0 px-4 py-6 sm:px-8 lg:px-12 lg:py-10">{children}</main>
    </div>
  );
}

export function PageTitle({ title, sub, right }: { title: string; sub?: string; right?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-[34px] font-bold leading-tight tracking-tight">{title}</h1>
        {sub && <p className="mt-1.5 max-w-2xl text-[16px] text-ink-soft">{sub}</p>}
      </div>
      {right}
    </div>
  );
}
