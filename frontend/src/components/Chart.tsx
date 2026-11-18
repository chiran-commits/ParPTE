import type { Chart as ChartT } from "../lib/types";

const COLORS = ["#0F5C4A", "#E9A20C", "#5B8DB8", "#C8432F", "#7A847F", "#9A6FB0"];

/** Renders Describe Image prompts (bar, line, pie, process) as clean exam-style SVG. */
export function Chart({ chart }: { chart: ChartT }) {
  const W = 640;
  const H = 360;
  return (
    <figure className="rounded-panel border border-line bg-white p-4">
      <figcaption className="mb-2 text-center font-display text-[17px] font-semibold">{chart.title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={chart.title}>
        {chart.type === "bar" && <Bars c={chart} W={W} H={H} />}
        {chart.type === "line" && <Lines c={chart} W={W} H={H} />}
        {chart.type === "pie" && <Pie c={chart} W={W} H={H} />}
        {chart.type === "process" && <Process c={chart} W={W} H={H} />}
      </svg>
      {chart.series.length > 1 && (
        <div className="mt-2 flex justify-center gap-5 text-sm">
          {chart.series.map((s, i) => (
            <span key={s.name} className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-sm" style={{ background: COLORS[i] }} />
              {s.name}
            </span>
          ))}
        </div>
      )}
    </figure>
  );
}

type P = { c: ChartT; W: number; H: number };

function axis(c: ChartT) {
  const max = Math.max(...c.series.flatMap((s) => s.values));
  const step = max > 60 ? 20 : max > 30 ? 10 : 5;
  const top = Math.ceil(max / step) * step;
  return { top, ticks: Array.from({ length: top / step + 1 }, (_, i) => i * step) };
}

function Grid({ c, W, H, top, ticks }: P & { top: number; ticks: number[] }) {
  const L = 48, B = H - 36;
  return (
    <g fontSize="12" fill="#4A5550">
      {ticks.map((t) => {
        const y = B - (t / top) * (B - 12);
        return (
          <g key={t}>
            <line x1={L} x2={W - 8} y1={y} y2={y} stroke="#ECEEEA" />
            <text x={L - 8} y={y + 4} textAnchor="end">
              {t}
              {c.unit === "%" ? "%" : ""}
            </text>
          </g>
        );
      })}
      <line x1={L} x2={W - 8} y1={B} y2={B} stroke="#7A847F" />
    </g>
  );
}

function Bars({ c, W, H }: P) {
  const { top, ticks } = axis(c);
  const L = 48, B = H - 36, inner = W - L - 16;
  const gw = inner / c.labels.length;
  const bw = Math.min(34, (gw * 0.7) / c.series.length);
  return (
    <g>
      <Grid c={c} W={W} H={H} top={top} ticks={ticks} />
      {c.labels.map((lab, i) => (
        <g key={lab}>
          {c.series.map((s, j) => {
            const h = (s.values[i] / top) * (B - 12);
            const x = L + 8 + gw * i + gw / 2 - (bw * c.series.length) / 2 + j * bw;
            return (
              <g key={s.name}>
                <rect x={x} y={B - h} width={bw - 3} height={h} fill={COLORS[j]} rx="2" />
                <text x={x + (bw - 3) / 2} y={B - h - 4} fontSize="11" textAnchor="middle" fill="#17201C">
                  {s.values[i]}
                </text>
              </g>
            );
          })}
          <text x={L + 8 + gw * i + gw / 2} y={B + 18} fontSize="12.5" textAnchor="middle" fill="#17201C">
            {lab}
          </text>
        </g>
      ))}
    </g>
  );
}

function Lines({ c, W, H }: P) {
  const { top, ticks } = axis(c);
  const L = 48, B = H - 36, inner = W - L - 24;
  const x = (i: number) => L + 12 + (inner / (c.labels.length - 1)) * i;
  return (
    <g>
      <Grid c={c} W={W} H={H} top={top} ticks={ticks} />
      {c.series.map((s, j) => (
        <g key={s.name}>
          <polyline fill="none" stroke={COLORS[j]} strokeWidth="2.5" points={s.values.map((v, i) => `${x(i)},${B - (v / top) * (B - 12)}`).join(" ")} />
          {s.values.map((v, i) => (
            <circle key={i} cx={x(i)} cy={B - (v / top) * (B - 12)} r="3.5" fill="white" stroke={COLORS[j]} strokeWidth="2" />
          ))}
        </g>
      ))}
      {c.labels.map((lab, i) => (
        <text key={lab} x={x(i)} y={B + 18} fontSize="12.5" textAnchor="middle" fill="#17201C">
          {lab}
        </text>
      ))}
    </g>
  );
}

function Pie({ c, W, H }: P) {
  const vals = c.series[0].values;
  const total = vals.reduce((a, b) => a + b, 0);
  const cx = W * 0.33, cy = H / 2, r = H * 0.4;
  let a0 = -Math.PI / 2;
  return (
    <g>
      {vals.map((v, i) => {
        const a1 = a0 + (v / total) * Math.PI * 2;
        const large = a1 - a0 > Math.PI ? 1 : 0;
        const d = `M${cx},${cy} L${cx + r * Math.cos(a0)},${cy + r * Math.sin(a0)} A${r},${r} 0 ${large} 1 ${cx + r * Math.cos(a1)},${cy + r * Math.sin(a1)} Z`;
        const mid = (a0 + a1) / 2;
        a0 = a1;
        return (
          <g key={i}>
            <path d={d} fill={COLORS[i % COLORS.length]} stroke="white" strokeWidth="2" />
            {v / total > 0.06 && (
              <text x={cx + r * 0.62 * Math.cos(mid)} y={cy + r * 0.62 * Math.sin(mid) + 5} textAnchor="middle" fontSize="14" fontWeight="700" fill="white">
                {v}%
              </text>
            )}
          </g>
        );
      })}
      {c.labels.map((lab, i) => (
        <g key={lab} transform={`translate(${W * 0.62}, ${60 + i * 34})`} fontSize="14" fill="#17201C">
          <rect width="14" height="14" y="-11" rx="2" fill={COLORS[i % COLORS.length]} />
          <text x="22">
            {lab} — {vals[i]}%
          </text>
        </g>
      ))}
    </g>
  );
}

function Process({ c, W, H }: P) {
  const n = c.labels.length;
  const cols = Math.min(3, n);
  const rows = Math.ceil(n / cols);
  const bw = 170, bh = 64, gx = (W - cols * bw) / (cols + 1), gy = (H - rows * bh) / (rows + 1);
  const pos = (i: number) => {
    const r = Math.floor(i / cols);
    const col = r % 2 === 0 ? i % cols : cols - 1 - (i % cols); // snake layout
    return { x: gx + col * (bw + gx), y: gy + r * (bh + gy) };
  };
  return (
    <g>
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="#0F5C4A" />
        </marker>
      </defs>
      {c.labels.slice(0, -1).map((_, i) => {
        const a = pos(i), b = pos(i + 1);
        const sameRow = a.y === b.y;
        const x1 = sameRow ? (b.x > a.x ? a.x + bw : a.x) : a.x + bw / 2;
        const x2 = sameRow ? (b.x > a.x ? b.x : b.x + bw) : b.x + bw / 2;
        const y1 = sameRow ? a.y + bh / 2 : a.y + bh, y2 = sameRow ? b.y + bh / 2 : b.y;
        return <line key={i} x1={x1} y1={y1} x2={x2 + (sameRow ? (b.x > a.x ? -4 : 4) : 0)} y2={y2 - (sameRow ? 0 : 4)} stroke="#0F5C4A" strokeWidth="2" markerEnd="url(#arrow)" />;
      })}
      {c.labels.map((lab, i) => {
        const p = pos(i);
        return (
          <g key={lab}>
            <rect x={p.x} y={p.y} width={bw} height={bh} rx="8" fill="#E3EFEA" stroke="#0F5C4A" />
            <text x={p.x + 14} y={p.y + 22} fontSize="12" fill="#0F5C4A" fontWeight="700">
              Stage {i + 1}
            </text>
            <text x={p.x + 14} y={p.y + 44} fontSize="14" fill="#17201C">
              {lab}
            </text>
          </g>
        );
      })}
    </g>
  );
}
