import type { Alert } from "../types";
import { STATE_TOKENS } from "../state";
import { localDm, localSpanSeconds } from "../api/dates";

/**
 * Dernières alertes — les vraies lignes de la table ALERTS.
 *
 * Une alerte ouverte porte sa couleur ; une alerte résolue est
 * explicitement marquée « rétablie » (notification de rétablissement
 * de l'étape 3), avec sa durée. Rien n'est inventé : si la table est
 * vide, on le dit.
 */
export function AlertsList({ alerts }: { alerts: Alert[] }) {
  if (alerts.length === 0) {
    return (
      <div className="flex h-full min-h-[140px] items-center justify-center rounded-sm border border-dashed border-[var(--color-rule)] px-4 text-center">
        <p className="text-sm text-[var(--color-ink-faint)]">
          Aucune alerte enregistrée pour l'instant.
        </p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col divide-y divide-[var(--color-rule)]">
      {alerts.map((a) => {
        const dur = duration(a);
        return (
          <li key={a.alert_id} className="flex items-start gap-3 py-2.5">
            {/* Pastille d'état : WARNING / CRITICAL / NORMAL (rétabli) */}
            <span
              aria-hidden="true"
              className="mt-1.5 inline-block size-2 shrink-0 rounded-full"
              style={{
                backgroundColor: STATE_TOKENS[a.level].solid,
              }}
            />
            <div className="min-w-0 flex-1">
              <p className="text-sm leading-snug break-words text-[var(--color-ink)]">
                {a.message}
              </p>
              <p className="data mt-1 text-[10px]" style={{ color: "var(--color-ink-faint)" }}>
                {a.resource} · {localDm(a.started_at)}
                {a.status === "OPEN" ? (
                  <span style={{ color: STATE_TOKENS[a.level].onTint }}>
                    {" "}
                    · en cours
                  </span>
                ) : (
                  <>
                    {" "}
                    · rétablie le {localDm(a.resolved_at ?? a.started_at)}
                    {dur && (
                      <>
                        {" "}
                        (durée {dur})
                      </>
                    )}
                  </>
                )}
              </p>
            </div>
            {typeof a.value_percent === "number" && (
              <span
                className="data shrink-0 text-xs"
                style={{ color: STATE_TOKENS[a.level].onTint }}
              >
                {a.value_percent.toFixed(1)} %
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Durée d'une alerte. Pour un rétablissement, resolved_at est null :
 * l'horodatage de fin est alors started_at (même horodatage → null).
 */
function duration(a: Alert): string | null {
  const endIso =
    a.resolved_at ?? (a.status === "RESOLVED" ? a.started_at : null);
  if (!endIso) return null;
  const seconds = localSpanSeconds(a.started_at, endIso);
  if (Number.isNaN(seconds) || seconds <= 0) return null;
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${seconds % 60} s`;
}
