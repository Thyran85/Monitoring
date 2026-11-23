import { useState } from "react";

import { testTelegram } from "./api/client";
import { AlertsList } from "./components/AlertsList";
import { HistoryChart } from "./components/HistoryChart";
import {
  CpuCores,
  DiskSplit,
  RamSplit,
} from "./components/MetricDetails";
import { MetricCard } from "./components/MetricCard";
import { StateBand } from "./components/StateBand";
import { STATE_TOKENS } from "./state";
import { useDashboard } from "./hooks/useDashboard";
import type { Resource } from "./types";

const RESOURCES: Resource[] = ["CPU", "RAM", "DISK"];

/**
 * Dashboard de surveillance — page unique.
 *
 * Hiérarchie : l'état général d'abord (bande), puis les trois
 * ressources (cartes), puis la preuve (courbe + alertes).
 * Toutes les valeurs viennent de l'API Flask (psutil + Oracle).
 */
export default function App() {
  const { status, history, alerts, error, updatedAt, loading } =
    useDashboard(5000);
  const [chartResource, setChartResource] = useState<Resource>("CPU");

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-paper)]">
        <p className="eyebrow">Chargement des mesures…</p>
      </div>
    );
  }

  const metrics = status?.metrics ?? null;
  const states = status?.states;
  const thresholds = status?.thresholds;

  // L'état du graphe est l'état de la ressource affichée, pas l'état
  // général : la courbe et la carte parlent la même couleur.
  const chartState = states?.[chartResource] ?? "NORMAL";

  return (
    <div className="min-h-screen bg-[var(--color-paper)]">
      {/* Barre technique : machine, version, rafraîchissement */}
      <div className="border-b border-[var(--color-rule)] bg-[var(--color-surface)]">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-2.5 sm:px-6 lg:px-8">
          <p className="data text-xs text-[var(--color-ink-soft)]">
            {metrics ? "Fedora local" : "machine locale"} · surveillance
            système
          </p>
          <p className="data text-[11px] text-[var(--color-ink-faint)]">
            {updatedAt
              ? `mise à jour ${new Date(updatedAt).toLocaleTimeString("fr-FR")}`
              : "jamais mise à jour"}
            {status && ` · ${status.monitor.interval_seconds} s par mesure`}
          </p>
        </div>
      </div>

      <StateBand status={status} error={error} />

      <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
        {/* Trois ressources */}
        {metrics && states && thresholds ? (
          <div className="grid grid-cols-1 gap-4 pt-6 md:grid-cols-3">
            <MetricCard
              resource="CPU"
              label="Processeur"
              value={metrics.cpu.percent}
              unit="%"
              state={states.CPU}
              thresholds={thresholds.CPU}
            >
              <CpuCores cpu={metrics.cpu} thresholds={thresholds.CPU} />
            </MetricCard>

            <MetricCard
              resource="RAM"
              label="Mémoire vive"
              value={metrics.ram.percent}
              unit="%"
              state={states.RAM}
              thresholds={thresholds.RAM}
            >
              <RamSplit ram={metrics.ram} />
            </MetricCard>

            <MetricCard
              resource="DISK"
              label={`Disque ${metrics.disk.path}`}
              value={metrics.disk.percent}
              unit="%"
              state={states.DISK}
              thresholds={thresholds.DISK}
            >
              <DiskSplit disk={metrics.disk} />
            </MetricCard>
          </div>
        ) : (
          <div className="pt-6">
            <p className="rounded-sm border border-dashed border-[var(--color-rule)] bg-[var(--color-surface)] p-6 text-center text-sm text-[var(--color-ink-faint)]">
              Aucune mesure disponible — le moniteur collecte sa première
              mesure.
            </p>
          </div>
        )}

        {/* Preuve : tendance + alertes */}
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-5">
          <section className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] p-4 sm:p-5 lg:col-span-3">
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="eyebrow">Tendance</p>
              <div role="tablist" aria-label="Ressource affichée" className="flex gap-1">
                {RESOURCES.map((r) => {
                  const active = r === chartResource;
                  return (
                    <button
                      key={r}
                      role="tab"
                      aria-selected={active}
                      onClick={() => setChartResource(r)}
                      className="data cursor-pointer rounded-sm px-2.5 py-1 text-[11px] uppercase tracking-wider transition-colors"
                      style={{
                        backgroundColor: active
                          ? STATE_TOKENS[states?.[r] ?? "NORMAL"].tint
                          : "transparent",
                        color: active
                          ? STATE_TOKENS[states?.[r] ?? "NORMAL"].onTint
                          : "var(--color-ink-faint)",
                        border: `1px solid ${
                          active
                            ? STATE_TOKENS[states?.[r] ?? "NORMAL"].onTint
                            : "var(--color-rule)"
                        }`,
                      }}
                    >
                      {r}
                    </button>
                  );
                })}
              </div>
            </div>
            {thresholds ? (
              <HistoryChart
                history={history}
                resource={chartResource}
                thresholds={thresholds[chartResource]}
                state={chartState}
              />
            ) : (
              <div className="mt-3 flex h-[180px] items-center justify-center rounded-sm border border-dashed border-[var(--color-rule)] px-4 text-center">
                <p className="text-sm text-[var(--color-ink-faint)]">
                  Tendance indisponible — le backend ne répond pas.
                </p>
              </div>
            )}
          </section>

          <section className="rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] p-4 sm:p-5 lg:col-span-2">
            <div className="mb-1 flex items-baseline justify-between gap-3">
              <p className="eyebrow">Dernières alertes</p>
              <p className="data text-[10px] text-[var(--color-ink-faint)]">
                {alerts.length}
              </p>
            </div>
            <AlertsList alerts={alerts} />
          </section>
        </div>

        {/* État des services + test Telegram (étape 4) */}
        <footer className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--color-rule)] pt-4">
          <div className="data flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-[var(--color-ink-faint)]">
            <span>
              Base Oracle&nbsp;:{" "}
              {status?.database.available
                ? `connectée (${status.database.instance ?? "?"})`
                : status?.database.error
                  ? `indisponible — ${status.database.error}`
                  : "—"}
            </span>
            <span>
              Telegram&nbsp;:{" "}
              {status?.telegram.configured ? "configuré" : "non configuré"}
            </span>
            <span>
              Dernière valeur globale&nbsp;:{" "}
              {status ? status.overall_state : "—"}
            </span>
          </div>
          <TelegramTestButton configured={status?.telegram.configured ?? false} />
        </footer>
      </main>
    </div>
  );
}

/** Bouton de test d'envoi Telegram — appelle vraiment l'API (étape 4). */
function TelegramTestButton({ configured }: { configured: boolean }) {
  const [result, setResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onClick = async () => {
    setBusy(true);
    setResult(null);
    try {
      const res = await testTelegram();
      setResult(res.detail);
    } catch (err) {
      setResult(err instanceof Error ? err.message : "erreur inconnue");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      {result && (
        <span role="status" className="data text-[11px] text-[var(--color-ink-soft)]">
          {result}
        </span>
      )}
      <button
        type="button"
        onClick={() => void onClick()}
        disabled={busy}
        className="data cursor-pointer rounded-sm border border-[var(--color-rule)] bg-[var(--color-surface)] px-3 py-1.5 text-[11px] uppercase tracking-wider text-[var(--color-ink-soft)] transition-colors hover:border-[var(--color-ink)] hover:text-[var(--color-ink)] disabled:cursor-wait disabled:opacity-60"
      >
        {busy ? "envoi…" : configured ? "Tester Telegram" : "Telegram non configuré"}
      </button>
    </div>
  );
}
