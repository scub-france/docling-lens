/**
 * Wire types — mirror the backend Pydantic schemas (`api/schemas.py`).
 *
 * The backend serializes camelCase (alias_generator=to_camel), so these
 * stay camelCase on the wire. The `payload` blob is whatever the agent
 * produced for that step — `READ` steps carry the upstream
 * `RAGIteration` shape (snake_case keys), which is why it's typed as a
 * loose record.
 */

export type ReasoningStepKind =
  | 'plan'
  | 'retrieve'
  | 'rerank'
  | 'read'
  | 'verify'
  | 'answer'
  | 'map'

export interface ReasoningStep {
  id: string
  kind: ReasoningStepKind
  title: string
  summary: string
  durationMs: number
  tokenCount: number
  citations: string[]
  payload: Record<string, unknown>
}

export interface ReasoningTrace {
  answer: string
  converged: boolean
  steps: ReasoningStep[]
  totalDurationMs: number
  tokensIn: number
  tokensOut: number
  modelId: string
}

export interface ReasoningRunRequest {
  documentJson: string
  query: string
  modelId?: string
}

/**
 * Single turn in the conversation pane. `trace` is set once the backend
 * responds; until then the assistant message is in `pending` state.
 */
export interface ConversationTurn {
  id: string
  query: string
  pendingAt: number
  trace: ReasoningTrace | null
  errorMessage: string | null
}
