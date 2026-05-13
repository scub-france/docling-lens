/**
 * Wire types for the enrich feature — mirror the backend Pydantic
 * schemas in `api/schemas.py`. Names stay in lockstep with the Python
 * `EnrichOperation` StrEnum so the wire contract is symmetric.
 */

export type EnrichOperation = 'summarize' | 'keywords' | 'entities'

export const ALL_ENRICH_OPERATIONS: readonly EnrichOperation[] = [
  'summarize',
  'keywords',
  'entities',
] as const

/** Concrete shape of one entity emitted by `_generate_entities` upstream. */
export interface EntityMention {
  entity_type: string
  mention: string
}

export interface NodeEnrichment {
  selfRef: string
  operation: EnrichOperation
  /**
   * Operation-specific payload (mirrors docling-agent v0.1.0):
   *   summarize → string                      (single short paragraph)
   *   keywords  → string[]                    (3–7 keywords)
   *   entities  → EntityMention[]             (entity_type + mention)
   *
   * Typed as `unknown` here because the wire is `Any`; the timeline
   * renderer narrows the shape per operation.
   */
  value: unknown
}

export interface EnrichTrace {
  documentJson: string
  enrichments: NodeEnrichment[]
  operations: EnrichOperation[]
  totalDurationMs: number
  modelId: string
}

export interface EnrichRunRequest {
  documentJson: string
  operations: EnrichOperation[]
  modelId?: string
}

/**
 * One historical run, including which ops the user asked for, what the
 * agent produced, and any error message. Pending state is captured by
 * `trace=null && errorMessage=null`.
 */
export interface EnrichRun {
  id: string
  operations: EnrichOperation[]
  pendingAt: number
  trace: EnrichTrace | null
  errorMessage: string | null
}
