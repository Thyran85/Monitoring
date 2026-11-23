import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { HistoryPoint, Resource, State } from "../types";
import { STATE_TOKENS } from "../state";
import { localHm } from "../api/dates";

/**
 * Tendance de la ressource sélectionnée sur les dernières mesures.
 *
 * Série unique (la ressource choisie) : pas de multi-courbes
 * décoratives. Les lignes de référence marquent les vrais seuils —
 * le graphe montre exactement la même règle que le moteur.
 */
export function HistoryChart({
  history,
  resource,
  thresholds,
  state,
}: {
  history: HistoryPoint[];
  resource: Resource;
  thresholds: { warning: number; critical: number };
  state: State;
}) {
  const key = resource === "CPU"
    ? "cpu_percent"
    : resource === "RAM"
      ? "ram_percent"
      : "disk_percent";

  const data = [...history]
    .reverse()
    .map((p) => ({
      t: localHm(p.collected_at),
      v: p[key],
    }))
    .filter((p): p is { t: string; v: number } => typeof p.v === "number");

  const color = STATE_TOKENS[state].bar;
  const empty = data.length === 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-baseline justify-between gap-3">
        <p className="eyebrow">{resource}</p>
        <p className="data text-[10px] text-[var(--color-ink-faint)]">
          {data.length} mesure{data.length > 1 ? "s" : ""}
        </p>
      </div>

      <div className="mt-3 min-h-[180px] flex-1">
        {empty ? (
          <div className="flex h-[180px] items-center justify-center rounded-sm border border-dashed border-[var(--color-rule)] px-4 text-center">
            <p className="text-sm text-[var(--color-ink-faint)]">
              Pas encore d'historique — les premières mesures arrivent
              dans quelques secondes.
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={data} margin={{ top: 4, right: 6, left: 4, bottom: 0 }}>
              <defs>
                <linearGradient id={`fill-${resource}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.22} />
                  <stop offset="100%" stopColor={color} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid
                stroke="var(--color-rule)"
                strokeDasharray="2 4"
                vertical={false}
              />
              <XAxis
                dataKey="t"
                tick={{ fontSize: 10, fill: "var(--color-ink-faint)", fontFamily: "var(--font-mono)" }}
                tickLine={false}
                axisLine={{ stroke: "var(--color-rule)" }}
                interval="preserveStartEnd"
                minTickGap={34}
              />
              <YAxis
                domain={[0, 100]}
                ticks={[0, 25, 50, 75, 100]}
                tick={{ fontSize: 10, fill: "var(--color-ink-faint)", fontFamily: "var(--font-mono)" }}
                tickLine={false}
                axisLine={false}
                width={44}
                tickMargin={4}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 2,
                  border: "1px solid var(--color-rule)",
                  background: "var(--color-surface)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                }}
                labelStyle={{ color: "var(--color-ink-soft)" }}
                formatter={(value) => [`${Number(value).toFixed(1)} %`, resource]}
              />
              {/* Seuils réels du moteur, tracés sur la courbe */}
              <ReferenceLine
                y={thresholds.warning}
                stroke="var(--color-warning)"
                strokeDasharray="4 3"
                strokeWidth={1}
              />
              <ReferenceLine
                y={thresholds.critical}
                stroke="var(--color-critical)"
                strokeDasharray="4 3"
                strokeWidth={1}
              />
              <Area
                type="monotone"
                dataKey="v"
                stroke={color}
                strokeWidth={2}
                fill={`url(#fill-${resource})`}
                dot={false}
                activeDot={{ r: 3, strokeWidth: 0 }}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="data mt-2 flex gap-4 text-[10px] text-[var(--color-ink-faint)]">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-px w-4 bg-[var(--color-warning)]" />
          seuil {thresholds.warning}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-px w-4 bg-[var(--color-critical)]" />
          seuil {thresholds.critical}
        </span>
      </div>
    </div>
  );
}
