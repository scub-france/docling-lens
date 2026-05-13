/**
 * RAG store — owns the conversation (turns + steps + model override).
 *
 * Doc state (filename, JSON, PDF, upload) lives in `useDocumentStore`
 * and is shared across features. Focus state (highlighted citations,
 * `focusTick`) also lives there — selecting a step here just *propagates*
 * the new citations to the document store, so the shared PDF / tree panes
 * react to RAG selections the same way they react to a future enrich
 * selection.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { runReasoning } from './api'
import type { ConversationTurn, ReasoningStep } from './types'
import { useDocumentStore } from '@/shared/stores/useDocumentStore'

let _turnSeq = 0
function nextTurnId(): string {
  _turnSeq += 1
  return `t${_turnSeq}_${Date.now().toString(36)}`
}

export const useRagStore = defineStore('rag', () => {
  const docStore = useDocumentStore()

  /** Conversation turns, in order. */
  const turns = ref<ConversationTurn[]>([])

  /** Selected (turn, step) — drives the trace pane focus. */
  const activeTurnId = ref<string | null>(null)
  const activeStepId = ref<string | null>(null)

  /** Model override the user typed in the composer; empty means default. */
  const modelOverride = ref<string>('')

  const activeTurn = computed<ConversationTurn | null>(
    () => turns.value.find((t) => t.id === activeTurnId.value) ?? null,
  )
  const activeStep = computed<ReasoningStep | null>(() => {
    const trace = activeTurn.value?.trace
    if (!trace || !activeStepId.value) return null
    return trace.steps.find((s) => s.id === activeStepId.value) ?? null
  })

  function selectStep(turnId: string, stepId: string | null): void {
    activeTurnId.value = turnId
    activeStepId.value = stepId
    // Propagate to the global focus — citations from the step (empty when
    // the step is deselected). `setFocus` bumps `focusTick` so the shared
    // panes re-scroll even when re-clicking the same step.
    docStore.setFocus(activeStep.value?.citations ?? [])
  }

  async function askQuestion(query: string): Promise<void> {
    const json = docStore.documentJson
    if (!json) throw new Error('Load a document before asking a question')
    const trimmed = query.trim()
    if (!trimmed) return

    const turn: ConversationTurn = {
      id: nextTurnId(),
      query: trimmed,
      pendingAt: Date.now(),
      trace: null,
      errorMessage: null,
    }
    turns.value.push(turn)
    activeTurnId.value = turn.id
    activeStepId.value = null

    try {
      const trace = await runReasoning({
        documentJson: json,
        query: trimmed,
        modelId: modelOverride.value.trim() || undefined,
      })
      const idx = turns.value.findIndex((t) => t.id === turn.id)
      if (idx >= 0) {
        turns.value[idx] = { ...turns.value[idx], trace }
      }
      // Auto-select the first step so the trace pane lights up immediately.
      if (trace.steps.length > 0) {
        activeStepId.value = trace.steps[0].id
        docStore.setFocus(trace.steps[0].citations)
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      const idx = turns.value.findIndex((t) => t.id === turn.id)
      if (idx >= 0) {
        turns.value[idx] = { ...turns.value[idx], errorMessage: message }
      }
    }
  }

  /** Wipe the conversation. Document state is managed by the doc store. */
  function resetConversation(): void {
    turns.value = []
    activeTurnId.value = null
    activeStepId.value = null
    modelOverride.value = ''
  }

  return {
    turns,
    activeTurnId,
    activeStepId,
    modelOverride,
    activeTurn,
    activeStep,
    selectStep,
    askQuestion,
    resetConversation,
  }
})
