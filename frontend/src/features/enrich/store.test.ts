import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useEnrichStore } from './store'
import type { EnrichTrace } from './types'
import { useDocumentStore } from '@/shared/stores/useDocumentStore'

vi.mock('./api', () => ({
  runEnrich: vi.fn(),
}))

import { runEnrich } from './api'

const sampleTrace: EnrichTrace = {
  documentJson: '{"body": {"children": []}}',
  enrichments: [
    { selfRef: '#/texts/0', operation: 'summarize', value: 'A short intro.' },
    { selfRef: '#/texts/0', operation: 'keywords', value: ['docling', 'pdf'] },
    {
      selfRef: '#/texts/0',
      operation: 'entities',
      value: [{ entity_type: 'ORG', mention: 'IBM' }],
    },
  ],
  operations: ['summarize', 'keywords', 'entities'],
  totalDurationMs: 4200,
  modelId: 'mistral-small3.2',
}

describe('useEnrichStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('defaults to summarize only', () => {
    const store = useEnrichStore()
    expect(Array.from(store.selectedOps)).toEqual(['summarize'])
  })

  it('toggleOp adds and removes ops', () => {
    const store = useEnrichStore()
    store.toggleOp('keywords')
    expect(Array.from(store.selectedOps).sort()).toEqual(['keywords', 'summarize'])
    store.toggleOp('summarize')
    expect(Array.from(store.selectedOps)).toEqual(['keywords'])
  })

  it('runWithSelected sends ops in canonical order', async () => {
    vi.mocked(runEnrich).mockResolvedValueOnce(sampleTrace)
    const store = useEnrichStore()
    const docStore = useDocumentStore()
    docStore.loadDocument('doc.json', '{}')

    // User picks in non-canonical order: keywords, then summarize.
    store.setOps(['keywords', 'summarize'])
    await store.runWithSelected()

    expect(runEnrich).toHaveBeenCalledTimes(1)
    const call = vi.mocked(runEnrich).mock.calls[0][0]
    // Canonical order: summarize before keywords (matches backend enum order).
    expect(call.operations).toEqual(['summarize', 'keywords'])
  })

  it('runWithSelected appends a pending run, resolves with the trace, focuses first ref', async () => {
    vi.mocked(runEnrich).mockResolvedValueOnce(sampleTrace)
    const store = useEnrichStore()
    const docStore = useDocumentStore()
    docStore.loadDocument('doc.json', '{}')

    await store.runWithSelected()

    expect(store.runs).toHaveLength(1)
    expect(store.runs[0].trace).toEqual(sampleTrace)
    expect(store.runs[0].errorMessage).toBeNull()
    // First enriched ref propagates to the shared focus.
    expect(docStore.focusedCitations).toEqual(['#/texts/0'])
  })

  it('runWithSelected records errorMessage when the call fails', async () => {
    vi.mocked(runEnrich).mockRejectedValueOnce(new Error('HTTP 503: not installed'))
    const store = useEnrichStore()
    const docStore = useDocumentStore()
    docStore.loadDocument('doc.json', '{}')

    await store.runWithSelected()

    expect(store.runs[0].trace).toBeNull()
    expect(store.runs[0].errorMessage).toContain('503')
  })

  it('runWithSelected rejects without a document', async () => {
    const store = useEnrichStore()
    await expect(store.runWithSelected()).rejects.toThrow(/Load a document/)
  })

  it('runWithSelected is a no-op when no ops are selected', async () => {
    const store = useEnrichStore()
    const docStore = useDocumentStore()
    docStore.loadDocument('doc.json', '{}')
    store.setOps([])

    await store.runWithSelected()

    expect(runEnrich).not.toHaveBeenCalled()
    expect(store.runs).toEqual([])
  })

  it('focusEnrichment propagates the ref to the doc store and bumps tick', () => {
    const store = useEnrichStore()
    const docStore = useDocumentStore()
    const tickBefore = docStore.focusTick

    store.focusEnrichment({
      selfRef: '#/texts/12',
      operation: 'summarize',
      value: 'x',
    })

    expect(docStore.focusedCitations).toEqual(['#/texts/12'])
    expect(docStore.focusTick).toBe(tickBefore + 1)
  })

  it('activeEnrichments tracks the active run only', async () => {
    vi.mocked(runEnrich).mockResolvedValueOnce(sampleTrace)
    const store = useEnrichStore()
    const docStore = useDocumentStore()
    docStore.loadDocument('doc.json', '{}')

    expect(store.activeEnrichments).toEqual([])
    await store.runWithSelected()
    expect(store.activeEnrichments).toHaveLength(3)

    store.selectRun(null)
    expect(store.activeEnrichments).toEqual([])
  })

  it('resetRuns wipes history and resets the composer', () => {
    const store = useEnrichStore()
    store.setOps(['keywords', 'entities'])
    store.modelOverride = 'llama3'
    store.runs.push({
      id: 'e1',
      operations: ['keywords'],
      pendingAt: 0,
      trace: sampleTrace,
      errorMessage: null,
    })

    store.resetRuns()

    expect(store.runs).toEqual([])
    expect(store.activeRunId).toBeNull()
    expect(store.modelOverride).toBe('')
    expect(Array.from(store.selectedOps)).toEqual(['summarize'])
  })
})
