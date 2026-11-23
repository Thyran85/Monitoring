/**
 * Types des réponses de l'API Flask (étape 5).
 * Aucun secret ici : l'API ne renvoie que des booléens pour Telegram.
 */

export type State = "NORMAL" | "WARNING" | "CRITICAL";
export type Resource = "CPU" | "RAM" | "DISK";

export interface Thresholds {
  warning: number;
  critical: number;
}

export interface CpuMetrics {
  percent: number;
  per_core: number[];
  core_count: number;
}

export interface RamMetrics {
  total_mb: number;
  used_mb: number;
  available_mb: number;
  percent: number;
}

export interface DiskMetrics {
  path: string;
  total_gb: number;
  used_gb: number;
  free_gb: number;
  percent: number;
}

export interface Snapshot {
  collected_at: string;
  cpu: CpuMetrics;
  ram: RamMetrics;
  disk: DiskMetrics;
}

export interface MonitorInfo {
  running: boolean;
  interval_seconds: number;
  confirm_samples: number;
  cycles: number;
  last_collect: string | null;
  disk_path: string;
}

export interface DatabaseInfo {
  available: boolean;
  error?: string;
  instance?: string;
  version?: string;
  container?: string;
  dsn?: string;
}

export interface StatusResponse {
  overall_state: State;
  states: Record<Resource, State>;
  thresholds: Record<Resource, Thresholds>;
  monitor: MonitorInfo;
  telegram: { configured: boolean };
  database: DatabaseInfo;
  metrics: Snapshot | null;
}

export interface HistoryPoint {
  collected_at: string;
  cpu_percent: number | null;
  ram_percent: number | null;
  disk_percent: number | null;
  ram_used_mb: number | null;
  disk_used_gb: number | null;
}

export interface HistoryResponse {
  count: number;
  metrics: HistoryPoint[];
}

export interface Alert {
  alert_id: number;
  resource: Resource;
  level: "WARNING" | "CRITICAL" | "NORMAL";
  message: string;
  value_percent: number | null;
  threshold: number | null;
  status: "OPEN" | "RESOLVED";
  started_at: string;
  resolved_at: string | null;
}

export interface AlertsResponse {
  count: number;
  alerts: Alert[];
}

export interface HealthResponse {
  status: string;
  monitor_running: boolean;
  cycles: number;
}
