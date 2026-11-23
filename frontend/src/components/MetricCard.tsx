import type { ReactNode } from "react";

import type { Resource, State, Thresholds } from "../types";
import { STATE_TOKENS } from "../state";
import { StatusBadge } from "./StatusBadge";
import { ThresholdGauge } from "./ThresholdGauge";

/**
 * Carte métrique : une ressource, une valeur, ses seuils, son état.
 *
 * La barre d'état en tête de carte reprend la couleur de l'état de
 * CETTE ressource (pas l'état général) : CPU peut être en CRITICAL
 * pendant que la carte affiche un bandeau rouge distinctement.
 */
export function MetricCard({
  resource,
  label,
  value,
  unit,
  decimals = 1,
  state,
  thresholds,
  children,
}: {
  resource: Resource;
  label: string;
  value: number;
  unit: string;
  decimals?: number;
  state: State;
  thresholds: Thresholds;
  /** Slot pour le détail (par cœur, répartition mémoire…). */
  children?: ReactNode;
}) {
  const tokens = STATE_TOKENS[state];

  return (
    <section
      className="relative overflow-hidden rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)]"
      aria-label={`${label} — état ${state}`}
    >
      {/* Barre d'état de la ressource */}
      <div
        aria-hidden="true"
        className="absolute inset-x-0 top-0 h-1"
        style={{ backgroundColor: tokens.bar }}
      />

      <div className="flex flex-col gap-4 p-4 pt-5 sm:p-5 sm:pt-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="eyebrow">{label}</p>
            <p className="mt-2 flex items-baseline gap-1">
              <span
                className="data text-[clamp(1.75rem,5vw,2.5rem)] leading-none font-semibold"
                style={{ color: "var(--color-ink)" }}
              >
                {value.toFixed(decimals)}
              </span>
              <span
                className="data text-sm"
                style={{ color: "var(--color-ink-soft)" }}
              >
                {unit}
              </span>
            </p>
          </div>
          <StatusBadge state={state} />
        </div>

        <ThresholdGauge
          value={value}
          thresholds={thresholds}
          state={state}
          resource={resource}
        />

        {children}
      </div>
    </section>
  );
}
