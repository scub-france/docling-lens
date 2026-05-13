/**
 * Enrich store — owns the run history + composer state (selected ops +
 * model override).
 *
 * Doc state + focus state live in `useDocumentStore`. When the user
 * clicks an enrichment in the timeline, we propagate the matching ref
 * to `docStore.setFocus([ref])`, which highlights the bbox in the PDF
 * and the matching node in the structure tree (same mechanism RAG uses
 * for step citations).
 *
 * We deliberately do NOT replace `docStore.documentJson` with the
 * enriched JSON: the structure tree + PDF always render the original
 * doc. Enrichments are surfaced as a side panel — not a destructive
 * mutation of the source.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { runEnrich } from './api'
import {
  ALL_ENRICH_OPERATIONS,
  type EnrichOperation,
  type EnrichRun,
  type NodeEnrichment,
} from './types'
import { useDocumentStore } from '@/shared/stores/useDocumentStore'

let _runSeq = 0
function nextRunId(): string {
  _runSeq += 1
  return `e${_runSeq}_${Date.now().toString(36)}`
}

export const useEnrichStore = defineStore('enrich', () => {
  const docStore = useDocumentStore()

  /**
   * Operations the user has currently selected in the composer. Start
   * with `summarize` only — it's the most useful single op and runs
   * fastest. The other three opt-in.
   */
  const selectedOps = ref<Set<EnrichOperation>>(new Set(['summarize']))

  /** Model override the user typed in the composer; empty = backend default. */
  const modelOverride = ref<string>('')

  /** Full history of runs in chronological order. */
  const runs = ref<EnrichRun[]>([])

  /** Currently inspected run — drives the timeline + status bar. */
  const activeRunId = ref<string | null>(null)
  const activeRun = computed<EnrichRun | null>(
    () => runs.value.find((r) => r.id === activeRunId.value) ?? null,
  )

  /** Flat list of enrichments from the active run — what the timeline renders. */
  const activeEnrichments = computed<NodeEnrichment[]>(
    () => activeRun.value?.trace?.enrichments ?? [],
  )

  function toggleOp(op: EnrichOperation): void {
    const next = new Set(selectedOps.value)
    if (next.has(op)) next.delete(op)
    else next.add(op)
    selectedOps.value = next
  }

  function setOps(ops: readonly EnrichOperation[]): void {
    selectedOps.value = new Set(ops)
  }

  /** Order ops canonically (UI consistency) before sending to the backend. */
  function _orderedOps(): EnrichOperation[] {
    return ALL_ENRICH_OPERATIONS.filter((op) => selectedOps.value.has(op))
  }

  async function runWithSelected(): Promise<void> {
    const json = docStore.documentJson
    if (!json) throw new Error('Load a document before running enrichments')
    const ops = _orderedOps()
    if (ops.length === 0) return

    const run: EnrichRun = {
      id: nextRunId(),
      operations: ops,
      pendingAt: Date.now(),
      trace: null,
      errorMessage: null,
    }
    runs.value.push(run)
    activeRunId.value = run.id

    try {
      const trace = await runEnrich({
        documentJson: json,
        operations: ops,
        modelId: modelOverride.value.trim() || undefined,
      })
      const idx = runs.value.findIndex((r) => r.id === run.id)
      if (idx >= 0) {
        runs.value[idx] = { ...runs.value[idx], trace }
      }
      // Auto-focus the first enriched ref so the right pane lights up.
      if (trace.enrichments.length > 0) {
        docStore.setFocus([trace.enrichments[0].selfRef])
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      const idx = runs.value.findIndex((r) => r.id === run.id)
      if (idx >= 0) {
        runs.value[idx] = { ...runs.value[idx], errorMessage: message }
      }
    }
  }

  function selectRun(runId: string | null): void {
    activeRunId.value = runId
  }

  function focusEnrichment(e: NodeEnrichment): void {
    docStore.setFocus([e.selfRef])
  }

  /** Wipe history + composer choices. Document state stays put. */
  function resetRuns(): void {
    runs.value = []
    activeRunId.value = null
    modelOverride.value = ''
    selectedOps.value = new Set(['summarize'])
  }

  return {
    selectedOps,
    modelOverride,
    runs,
    activeRunId,
    activeRun,
    activeEnrichments,
    toggleOp,
    setOps,
    runWithSelected,
    selectRun,
    focusEnrichment,
    resetRuns,
  }
})
