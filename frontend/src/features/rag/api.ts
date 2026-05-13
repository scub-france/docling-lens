import { apiFetch } from '@/shared/api/http'

import type { ReasoningRunRequest, ReasoningTrace } from './types'

/**
 * Kick off a `docling-agent` RAG run against the provided
 * `DoclingDocument` JSON and wait for the trace.
 *
 * No streaming yet — the backend blocks on `_rag_loop` and returns once
 * the loop converges or hits `max_iterations`. Runs typically take 20–40s;
 * the caller should show a pending state in the conversation pane.
 *
 * Errors (surfaced via `ApiError.status`):
 *  - 503 when `REASONING_ENABLED=false` or docling-agent isn't installed
 *  - 400 on empty query / empty document_json
 *  - 502 when the LLM couldn't produce a parseable answer
 *  - 500 on unexpected loop failures
 */
export function runReasoning(req: ReasoningRunRequest): Promise<ReasoningTrace> {
  return apiFetch<ReasoningTrace>('/api/reasoning', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
}
