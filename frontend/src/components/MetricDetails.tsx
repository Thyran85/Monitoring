import type { CpuMetrics, DiskMetrics, RamMetrics } from "../types";
import { STATE_TOKENS } from "../state";
import type { State } from "../types";

/**
 * Détail CPU : barres par cœur.
 * Chaque cœur est coloré selon SA propre valeur vis-à-vis des seuils
 * globaux — la couleur reste portée par un état, jamais décorative.
 */
export function CpuCores({ cpu, thresholds }: {
  cpu: CpuMetrics;
  thresholds: { warning: number; critical: number };
}) {
  const level = (v: number): State =>
    v >= thresholds.critical ? "CRITICAL" : v >= thresholds.warning ? "WARNING" : "NORMAL";

  return (
    <div>
      <p className="eyebrow">Par cœur — {cpu.core_count} logiques</p>
      <div className="mt-2 flex items-end gap-[3px]" role="list">
        {cpu.per_core.map((v, i) => {
          const color = STATE_TOKENS[level(v)].bar;
          return (
            <div
              key={i}
              role="listitem"
              className="group relative flex-1"
              title={`Cœur ${i} : ${v.toFixed(1)} %`}
            >
              <div
                className="w-full rounded-[1px]"
                style={{
                  height: `${Math.max(6, v * 0.62)}px`,
                  backgroundColor: color,
                  transition: "height 600ms ease",
                }}
              />
            </div>
          );
        })}
      </div>
      <div className="data mt-1.5 flex justify-between text-[10px] text-[var(--color-ink-faint)]">
        <span>0 %</span>
        <span>max {Math.max(...cpu.per_core).toFixed(0)} %</span>
      </div>
    </div>
  );
}

/** Détail RAM : répartition utilisée / disponible sur une seule piste. */
export function RamSplit({ ram }: { ram: RamMetrics }) {
  const usedPct = ram.percent;
  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="data text-[var(--color-ink-soft)]">
          {formatGb(ram.used_mb)} utilisée
        </span>
        <span className="data text-[var(--color-ink-soft)]">
          {formatGb(ram.available_mb)} dispo
        </span>
      </div>
      <div
        aria-hidden="true"
        className="mt-1.5 flex h-2 w-full overflow-hidden rounded-[2px] bg-[var(--color-rule)]"
      >
        <div
          className="h-full bg-[var(--color-ink)]"
          style={{ width: `${usedPct}%`, transition: "width 600ms ease" }}
        />
      </div>
      <p className="data mt-1.5 text-[10px] text-[var(--color-ink-faint)]">
        Total {formatGb(ram.total_mb)}
      </p>
    </div>
  );
}

/** Détail disque : capacité, occupation, espace libre. */
export function DiskSplit({ disk }: { disk: DiskMetrics }) {
  return (
    <dl className="grid grid-cols-3 gap-2 text-xs">
      <div>
        <dt className="eyebrow">Total</dt>
        <dd className="data mt-1 text-[var(--color-ink)]">
          {disk.total_gb.toFixed(0)} Go
        </dd>
      </div>
      <div>
        <dt className="eyebrow">Occupé</dt>
        <dd className="data mt-1 text-[var(--color-ink)]">
          {disk.used_gb.toFixed(1)} Go
        </dd>
      </div>
      <div>
        <dt className="eyebrow">Libre</dt>
        <dd className="data mt-1 text-[var(--color-ink)]">
          {disk.free_gb.toFixed(1)} Go
        </dd>
      </div>
    </dl>
  );
}

function formatGb(mb: number): string {
  return `${(mb / 1024).toFixed(1)} Go`;
}
