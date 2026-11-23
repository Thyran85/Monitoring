import type { State, StatusResponse } from "../types";
import { STATE_TOKENS } from "../state";
import { localHms } from "../api/dates";

/**
 * Bande d'état pleine largeur — le moment fort de la page.
 *
 * Le fond prend la couleur de l'état général : impossible de manquer
 * un WARNING ou un CRITICAL en ouvrant l'onglet. Le texte est blanc
 * sur les trois états (les teintes sont choisies profondes pour ça).
 *
 * En cas d'erreur API, on conserve le dernier état connu et on
 * annonce l'erreur en incrustation : on ne remplace jamais une
 * information par un blanc.
 */
export function StateBand({
  status,
  error,
}: {
  status: StatusResponse | null;
  error: string | null;
}) {
  const state: State = status?.overall_state ?? "NORMAL";
  const tokens = STATE_TOKENS[state];

  return (
    <header
      className="state-band w-full"
      style={{ backgroundColor: tokens.solid }}
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-5 px-4 py-6 sm:px-6 md:flex-row md:items-end md:justify-between md:py-8 lg:px-8">
        <div>
          <p
            className="eyebrow"
            style={{ color: "rgba(255, 255, 255, 0.72)" }}
          >
            État général du système
          </p>
          <p
            className="mt-2 text-[clamp(2.5rem,8vw,4.5rem)] leading-[0.9] font-bold tracking-[-0.03em]"
            style={{ color: "#ffffff" }}
          >
            {state}
          </p>
          <p
            className="mt-2 max-w-md text-sm"
            style={{ color: "rgba(255, 255, 255, 0.82)" }}
          >
            {status
              ? describe(status)
              : "Connexion au backend en cours…"}
          </p>
        </div>

        <div
          className="data flex flex-wrap items-center gap-x-5 gap-y-2 text-xs"
          style={{ color: "rgba(255, 255, 255, 0.82)" }}
        >
          <span>
            Mesure{" "}
            {status?.monitor.last_collect
              ? localHms(status.monitor.last_collect)
              : "—"}
          </span>
          <span>
            Cycle&nbsp;
            {status?.monitor.cycles ?? 0}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block size-2 rounded-full"
              style={{
                backgroundColor:
                  status?.monitor.running && !error
                    ? "#ffffff"
                    : "rgba(255, 255, 255, 0.4)",
              }}
            />
            {error ? "lien perdu" : status?.monitor.running ? "actif" : "arrêté"}
          </span>
          <span>actualisation 5&nbsp;s</span>
        </div>
      </div>

      {/* Annonce d'erreur : visible, mais sans effacer les données */}
      {error && (
        <div
          role="status"
          className="mx-auto max-w-6xl px-4 pb-4 sm:px-6 lg:px-8"
        >
          <p
            className="data rounded-sm px-3 py-2 text-xs"
            style={{
              backgroundColor: "rgba(0, 0, 0, 0.28)",
              color: "#ffffff",
            }}
          >
            Backend injoignable — {error}. Les valeurs affichées sont les
            dernières reçues.
          </p>
        </div>
      )}
    </header>
  );
}

function describe(status: StatusResponse): string {
  const normal = Object.entries(status.states)
    .filter(([, s]) => s === "NORMAL")
    .map(([r]) => r);
  const flagged = Object.entries(status.states)
    .filter(([, s]) => s !== "NORMAL")
    .map(([r, s]) => `${r} ${s}`);

  if (flagged.length === 0) {
    return `${normal.length} ressources sous les seuils — aucune anomalie confirmée.`;
  }
  return `${flagged.join(" · ")} — confirmé sur ${
    status.monitor.confirm_samples
  } mesures consécutives.`;
}
