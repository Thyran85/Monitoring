/**
 * Règles de présentation des états.
 *
 * La couleur n'est jamais décorative : elle vient toujours d'un
 * état. Ces mappings sont la seule source de vérité visuelle.
 */

import type { State } from "./types";

interface StateTokens {
  /** Couleur pleine (fond de bande, pastille). */
  solid: string;
  /** Fond très pâle (badges sur papier). */
  tint: string;
  /** Texte lisible sur le fond pâle. */
  onTint: string;
  /** Barre d'état de la carte. */
  bar: string;
}

export const STATE_TOKENS: Record<State, StateTokens> = {
  NORMAL: {
    solid: "var(--color-normal)",
    tint: "var(--color-normal-soft)",
    onTint: "var(--color-normal)",
    bar: "var(--color-normal)",
  },
  WARNING: {
    solid: "var(--color-warning)",
    tint: "var(--color-warning-soft)",
    onTint: "var(--color-warning)",
    bar: "var(--color-warning)",
  },
  CRITICAL: {
    solid: "var(--color-critical)",
    tint: "var(--color-critical-soft)",
    onTint: "var(--color-critical)",
    bar: "var(--color-critical)",
  },
};
