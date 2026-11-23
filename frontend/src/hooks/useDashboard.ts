/**
 * Hook de rafraîchissement automatique.
 *
 * Interroge les 3 endpoints utiles en parallière toutes les
 * `interval` millisecondes, conserve le dernier état connu (le
 * dashboard reste affiché si le backend tombe brièvement) et signale
 * l'erreur pour que l'interface puisse l'annoncer.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchAlerts, fetchHistory, fetchStatus } from "../api/client";
import type {
  AlertsResponse,
  HistoryResponse,
  StatusResponse,
} from "../types";

export interface DashboardData {
  status: StatusResponse | null;
  history: HistoryPoint[];
  alerts: AlertsResponse["alerts"];
  /** Erreur du dernier cycle (null si tout va bien). */
  error: string | null;
  /** Horodatage (ms) du dernier cycle réussi, null si jamais réussi. */
  updatedAt: number | null;
  /** Vrai pendant le tout premier chargement (aucun affichage avant). */
  loading: boolean;
}

type HistoryPoint = HistoryResponse["metrics"][number];

const INITIAL: DashboardData = {
  status: null,
  history: [],
  alerts: [],
  error: null,
  updatedAt: null,
  loading: true,
};

export function useDashboard(interval = 5000): DashboardData {
  const [data, setData] = useState<DashboardData>(INITIAL);
  const inFlight = useRef(false);

  const load = useCallback(async () => {
    // Un cycle ne doit jamais chevaucher le précédent.
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const [status, history, alerts] = await Promise.all([
        fetchStatus(),
        fetchHistory(60),
        fetchAlerts(12),
      ]);
      setData({
        status,
        history: history.metrics,
        alerts: alerts.alerts,
        error: null,
        updatedAt: Date.now(),
        loading: false,
      });
    } catch (err) {
      // On conserve les données précédentes : le dashboard reste
      // lisible, seul l'annonce d'erreur change.
      setData((prev) => ({
        ...prev,
        error: err instanceof Error ? err.message : "erreur inconnue",
        loading: false,
      }));
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), interval);
    return () => window.clearInterval(id);
  }, [load, interval]);

  return data;
}
