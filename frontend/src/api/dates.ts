/**
 * Lecture des horodatages de l'API — deux conventions naïves sont
 * en jeu (constatées à l'étape 6, voir docs/PHASE1_ETAPE6_RESULTATS.md) :
 *
 * - METRICS.collected_at : UTC naïf (« 2026-11-22 14:42:04 ») —
 *   généré par Python en UTC puis tronqué de son fuseau à l'insertion ;
 * - ALERTS.started_at / resolved_at : heure locale naïve
 *   (CURRENT_TIMESTAMP d'Oracle, fuseau de session du conteneur) ;
 * - status.monitor.last_collect : ISO 8601 explicite « …+00:00 ».
 *
 * Plutôt que de laisser `new Date()` deviner (résultat variable selon
 * le moteur), chaque convention est interprétée explicitement ici.
 */

const HAS_TZ = /(?:Z|[+-]\d{2}:?\d{2})$/;

/** Horodatage sans fuseau = UTC. Renvoie un Date instanciel exact. */
export function parseUtc(iso: string): Date {
  if (HAS_TZ.test(iso)) return new Date(iso);
  // « 2026-11-22 14:42:04[.fff…] » → ISO strict UTC.
  const normalized = iso.replace(" ", "T").replace(/(\.\d{3})\d+/, "$1");
  return new Date(`${normalized}Z`);
}

/** Horodatage sans fuseau = heure locale du poste. */
export function parseLocal(iso: string): Date {
  if (HAS_TZ.test(iso)) return new Date(iso);
  const m = iso.match(
    /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/,
  );
  if (!m) return new Date(iso);
  const [, y, mo, d, h, mi, s] = m;
  return new Date(+y, +mo - 1, +d, +h, +mi, +(s ?? 0));
}

/** Heure locale HH:MM:SS à partir d'un horodatage UTC. */
export function localHms(iso: string): string {
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(11, 19);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

/** Heure locale HH:MM à partir d'un horodatage UTC. */
export function localHm(iso: string): string {
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(11, 16);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Date/heure locale « JJ/MM HH:MM:SS » à partir d'un horodatage local naïf. */
export function localDm(iso: string | null): string {
  if (!iso) return "—";
  const d = parseLocal(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(
    d.getMinutes(),
  )}:${pad(d.getSeconds())}`;
}

/** Écart entre deux horodatages d'alerte (conventions identiques). */
export function localSpanSeconds(startIso: string, endIso: string): number {
  const start = parseLocal(startIso).getTime();
  const end = parseLocal(endIso).getTime();
  if (Number.isNaN(start) || Number.isNaN(end)) return NaN;
  return Math.round((end - start) / 1000);
}
