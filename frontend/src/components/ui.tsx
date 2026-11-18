import type { ButtonHTMLAttributes, ReactNode } from "react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "ghost" | "danger";

export function Button({ variant = "primary", className, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const v = {
    primary: "bg-pine text-white hover:bg-pine-deep disabled:bg-ink-mute",
    secondary: "bg-paper-raised text-ink border border-line hover:border-ink-mute",
    ghost: "text-ink-soft hover:text-ink hover:bg-paper-sunk",
    danger: "bg-coral text-white hover:brightness-95",
  }[variant];
  return (
    <button
      {...p}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-[15px] font-semibold transition-colors",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pine disabled:cursor-not-allowed",
        v,
        className,
      )}
    />
  );
}

export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("rounded-panel border border-line bg-paper-raised", className)}>{children}</div>;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-ink-soft" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-pine" />
      {label && <span>{label}</span>}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "error" | "warn"; children: ReactNode }) {
  const t = { info: "bg-pine-tint text-pine-deep", error: "bg-coral-tint text-coral", warn: "bg-marigold-tint text-ink" }[tone];
  return <div className={cx("rounded-md px-4 py-3 text-[15px]", t)}>{children}</div>;
}

/** The signature 10–90 scale. `value` fills in pine; `target` is the marigold marker. */
export function ScoreRuler({ value, target, label, compact = false }: { value: number | null | undefined; target?: number; label?: string; compact?: boolean }) {
  const pos = (v: number) => `${((Math.min(90, Math.max(10, v)) - 10) / 80) * 100}%`;
  const bands = [30, 50, 65, 79];
  return (
    <div className="w-full">
      {label && (
        <div className="mb-1.5 flex items-baseline justify-between">
          <span className={cx("font-display font-semibold", compact ? "text-[15px]" : "text-lg")}>{label}</span>
          <span className={cx("font-display font-bold tabular-nums", compact ? "text-xl" : "text-3xl", value == null && "text-ink-mute")}>
            {value ?? "—"}
          </span>
        </div>
      )}
      <div className={cx("relative rounded-full bg-paper-sunk", compact ? "h-2" : "h-3")}>
        {value != null && <div className="absolute inset-y-0 left-0 rounded-full bg-pine" style={{ width: pos(value) }} />}
        {bands.map((b) => (
          <span key={b} className="absolute top-0 h-full w-px bg-paper-raised/80" style={{ left: pos(b) }} />
        ))}
        {target != null && (
          <span className="absolute -top-1.5 -bottom-1.5 w-[3px] -translate-x-1/2 rounded bg-marigold" style={{ left: pos(target) }} title={`Target ${target}`} />
        )}
      </div>
      {!compact && (
        <div className="relative mt-1 h-4 text-[11px] tabular-nums text-ink-mute">
          {[10, ...bands, 90].map((b) => (
            <span key={b} className="absolute -translate-x-1/2" style={{ left: pos(b) }}>
              {b}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function TraitBar({ name, score, max, note }: { name: string; score: number; max: number; note?: string }) {
  const pct = max ? score / max : 0;
  const tone = pct >= 0.8 ? "bg-ok" : pct >= 0.5 ? "bg-marigold" : "bg-coral";
  return (
    <div>
      <div className="flex items-baseline justify-between gap-4 text-[15px]">
        <span className="font-semibold">{name}</span>
        <span className="tabular-nums text-ink-soft">
          <b className="text-ink">{Number.isInteger(score) ? score : score.toFixed(1)}</b> / {max}
        </span>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-paper-sunk">
        <div className={cx("h-full rounded-full", tone)} style={{ width: `${pct * 100}%` }} />
      </div>
      {note && <p className="mt-1 text-[13px] text-ink-mute">{note}</p>}
    </div>
  );
}

export function fmtTime(s: number) {
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.max(0, Math.floor(s % 60))).padStart(2, "0")}`;
}
