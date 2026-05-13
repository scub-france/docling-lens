import { apiFetch } from '@/shared/api/http'

import type { EnrichRunRequest, EnrichTrace } from './types'

/**
 * Run one or more enrichment operations (summarize / keywords / entities /
 * classify) on the supplied DoclingDocument JSON and wait for the trace.
 *
 * Like the RAG endpoint this is non-streaming today — the backend blocks
 * until every requested op has walked the doc. Latency scales with the
 * doc size * number of ops * Ollama call latency (think 30s for a 200-node
 * doc on `summarize`).
 *
 * Errors (surfaced via `ApiError.status`):
 *  - 503 when `REASONING_ENABLED=false` or docling-agent isn't installed
 *  - 400 on empty document_json / empty operations / unknown op name
 *  - 500 on unexpected agent failures
 */
export function runEnrich(req: EnrichRunRequest): Promise<EnrichTrace> {
  return apiFetch<EnrichTrace>('/api/enrich', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
}
