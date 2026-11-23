import type { State } from "../types";
import { STATE_TOKENS } from "../state";

/**
 * Pastille d'état : puce + mot, sur fond pâle teinté.
 * `compact` réduit au format pastille seule (listes d'alertes).
 */
export function StatusBadge({
  state,
  compact = false,
}: {
  state: State;
  compact?: boolean;
}) {
  const tokens = STATE_TOKENS[state];

  return (
    <span
      className="data inline-flex items-center gap-1.5 rounded-full font-medium whitespace-nowrap"
      style={{
        backgroundColor: tokens.tint,
        color: tokens.onTint,
        fontSize: compact ? "0.6875rem" : "0.75rem",
        letterSpacing: "0.06em",
        padding: compact ? "0.15rem 0.5rem" : "0.3rem 0.7rem",
        textTransform: "uppercase",
      }}
    >
      <span
        aria-hidden="true"
        className="inline-block size-1.5 rounded-full"
        style={{ backgroundColor: tokens.solid }}
      />
      {state}
    </span>
  );
}
