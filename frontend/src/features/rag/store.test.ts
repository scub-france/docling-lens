import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useRagStore } from './store'
import type { ReasoningTrace } from './types'
import { useDocumentStore } from '@/shared/stores/useDocumentStore'

vi.mock('./api', () => ({
  runReasoning: vi.fn(),
}))

import { runReasoning } from './api'

const sampleTrace: ReasoningTrace = {
  answer: '2.45 pages/sec',
  converged: true,
  steps: [
    {
      id: 's1',
      kind: 'read',
      title: 'Read #/texts/12',
      summary: 'M3 Max default = 2.45',
      durationMs: 187,
      tokenCount: 0,
      citations: ['#/texts/12'],
      payload: { section_ref: '#/texts/12' },
    },
  ],
  totalDurationMs: 1200,
  tokensIn: 100,
  tokensOut: 50,
  modelId: 'mistral-small3.2',
}

describe('useRagStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('askQuestion appends a pending turn and resolves with the trace', async () => {
    vi.mocked(runReasoning).mockResolvedValueOnce(sampleTrace)
    const store = useRagStore()
    const docStore = useDocumentStore()
    docStore.loadDocument('doc.json', '{}')

    await store.askQuestion('throughput?')

    expect(store.turns).toHaveLength(1)
    expect(store.turns[0].query).toBe('throughput?')
    expect(store.turns[0].trace).toEqual(sampleTrace)
    expect(store.turns[0].errorMessage).toBeNull()
    // First step auto-selected so the trace pane lights up immediately.
    expect(store.activeStepId).toBe('s1')
    // The step's citations propagated to the shared doc store.
    expect(docStore.focusedCitations).toEqual(['#/texts/12'])
  })

  it('askQuestion records errorMessage when the call fails', async () => {
    vi.mocked(runReasoning).mockRejectedValueOnce(new Error('HTTP 503: nope'))
    const store = useRagStore()
    const docStore = useDocumentStore()
    docStore.loadDocument('doc.json', '{}')

    await store.askQuestion('whatever')

    expect(store.turns[0].trace).toBeNull()
    expect(store.turns[0].errorMessage).toContain('503')
  })

  it('askQuestion rejects without a document', async () => {
    const store = useRagStore()
    await expect(store.askQuestion('x')).rejects.toThrow(/Load a document/)
  })

  it('selectStep propagates the step citations to the doc store and bumps tick', () => {
    const store = useRagStore()
    const docStore = useDocumentStore()
    docStore.loadDocument('doc.json', '{}')
    store.turns.push({
      id: 't1',
      query: 'q',
      pendingAt: 0,
      trace: sampleTrace,
      errorMessage: null,
    })

    const tickBefore = docStore.focusTick
    store.selectStep('t1', 's1')

    expect(docStore.focusedCitations).toEqual(['#/texts/12'])
    expect(docStore.focusTick).toBe(tickBefore + 1)
  })

  it('selectStep with null stepId clears focus citations', () => {
    const store = useRagStore()
    const docStore = useDocumentStore()
    store.turns.push({
      id: 't1',
      query: 'q',
      pendingAt: 0,
      trace: sampleTrace,
      errorMessage: null,
    })
    store.selectStep('t1', 's1')
    expect(docStore.focusedCitations).toEqual(['#/texts/12'])

    store.selectStep('t1', null)
    expect(docStore.focusedCitations).toEqual([])
  })

  it('resetConversation wipes turns + selection + model override', () => {
    const store = useRagStore()
    store.turns.push({
      id: 't',
      query: 'q',
      pendingAt: 0,
      trace: sampleTrace,
      errorMessage: null,
    })
    store.selectStep('t', 's1')
    store.modelOverride = 'mistral-small3.2'

    store.resetConversation()

    expect(store.turns).toEqual([])
    expect(store.activeTurnId).toBeNull()
    expect(store.activeStepId).toBeNull()
    expect(store.modelOverride).toBe('')
  })
})
