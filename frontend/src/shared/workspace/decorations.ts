/**
 * Tree decorations — feature-agnostic visual hints attached to a node
 * by its `self_ref`.
 *
 * `DocumentPane` lives in `shared/` and must not depend on any feature
 * (RAG, enrich, …). Features wanting to decorate the tree compute a
 * `DecorationsMap` from their own state and pass it down as a prop;
 * the pane renders the badges blindly.
 *
 * Example — the enrich feature emits one decoration per
 * (selfRef, operation) pair with `badge` being a single letter and
 * `tooltip` being the rendered enrichment value.
 */

export type DecorationColor = 'green' | 'blue' | 'amber' | 'purple' | 'mute' | 'gray'

export interface NodeDecoration {
  /** Short text rendered inside the badge — keep ≤ 2 chars so it fits. */
  badge: string
  color: DecorationColor
  /** Full content shown as a native tooltip on hover. */
  tooltip?: string
}

export type DecorationsMap = ReadonlyMap<string, readonly NodeDecoration[]>

/** Empty constant — reused by callers (and the prop default) so we
 *  don't allocate a fresh Map on every render that doesn't decorate. */
export const NO_DECORATIONS: DecorationsMap = new Map()
