/**
 * Client de l'API — toutes les données du dashboard viennent d'ici,
 * donc de Flask, donc de psutil/Oracle. Aucune donnée fictive.
 *
 * Les chemins sont relatifs (/api) : en développement, le proxy Vite
 * transmet au backend ; en production, même origine.
 */

import type {
  AlertsResponse,
  HistoryResponse,
  StatusResponse,
} from "../types";

const TIMEOUT_MS = 8000;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(path, {
      ...init,
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = (await response.json()) as { error?: string };
        if (body.error) detail = body.error;
      } catch {
        // réponse non JSON : on garde le statut HTTP
      }
      throw new ApiError(detail, response.status);
    }
    return (await response.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("backend injoignable (délai dépassé)", 0);
    }
    throw new ApiError("backend injoignable", 0);
  } finally {
    clearTimeout(timer);
  }
}

export const fetchStatus = () => request<StatusResponse>("/api/status");

export const fetchHistory = (limit = 60) =>
  request<HistoryResponse>(`/api/metrics/history?limit=${limit}`);

export const fetchAlerts = (limit = 12) =>
  request<AlertsResponse>(`/api/alerts?limit=${limit}`);

/** Teste la configuration Telegram (étape 4). */
export async function testTelegram(): Promise<{
  ok: boolean;
  detail: string;
  configured: boolean;
}> {
  return request("/api/alerts/test", { method: "POST" });
}
