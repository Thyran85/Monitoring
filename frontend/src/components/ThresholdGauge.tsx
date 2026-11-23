import type { Resource, State, Thresholds } from "../types";
import { STATE_TOKENS } from "../state";

/**
 * Jauge à seuils zonés — l'élément signature du dashboard.
 *
 * Contrairement à une barre de progression neutre, la piste IMPRIME
 * physiquement les zones WARNING et CRITICAL : on voit non seulement
 * où on en est, mais combien de place reste avant la falaise.
 *
 *   0 ─────────── 75 ═══════ 90 ░░░░ 100
 *   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓   ← remplissage = valeur
 *        attention      critique
 *
 * Accessibilité : rôle="meter" avec aria-valuenow/min/max et un
 * libellé décrivant la valeur en clair.
 */
export function ThresholdGauge({
  value,
  thresholds,
  state,
  resource,
}: {
  value: number;
  thresholds: Thresholds;
  state: State;
  resource: Resource;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const fill = STATE_TOKENS[state].bar;
  const warn = thresholds.warning;
  const crit = thresholds.critical;

  return (
    <div>
      <div
        role="meter"
        aria-valuenow={Math.round(clamped)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${resource} : ${clamped.toFixed(1)} %, seuils ${warn} % et ${crit} %`}
        className="relative h-3 w-full overflow-hidden rounded-[2px] bg-[var(--color-rule)]"
      >
        {/* Zones de seuil imprimées sur la piste */}
        <div
          aria-hidden="true"
          className="absolute inset-y-0 bg-[var(--color-warning-soft)]"
          style={{ left: `${warn}%`, width: `${crit - warn}%` }}
        />
        <div
          aria-hidden="true"
          className="absolute inset-y-0 bg-[var(--color-critical-soft)]"
          style={{ left: `${crit}%`, right: 0 }}
        />

        {/* Marqueurs de seuil : filets pleins, visibles sur la valeur */}
        <div
          aria-hidden="true"
          className="absolute inset-y-0 w-px bg-[var(--color-warning)]"
          style={{ left: `${warn}%` }}
        />
        <div
          aria-hidden="true"
          className="absolute inset-y-0 w-px bg-[var(--color-critical)]"
          style={{ left: `${crit}%` }}
        />

        {/* Remplissage = valeur mesurée */}
        <div
          aria-hidden="true"
          className="absolute inset-y-0 left-0"
          style={{
            width: `${clamped}%`,
            backgroundColor: fill,
            transition: "width 600ms ease",
          }}
        />
      </div>

      {/* Annotations de seuil, alignées sous leurs marqueurs */}
      <div className="relative mt-1 h-3.5">
        <span
          className="data absolute -translate-x-1/2 text-[10px] leading-none"
          style={{
            left: `${warn}%`,
            color: "var(--color-warning)",
          }}
        >
          {warn}
        </span>
        <span
          className="data absolute -translate-x-1/2 text-[10px] leading-none"
          style={{
            left: `${crit}%`,
            color: "var(--color-critical)",
          }}
        >
          {crit}
        </span>
      </div>
    </div>
  );
}
