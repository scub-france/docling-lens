import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAppStore } from './useAppStore'

vi.mock('@/shared/api/health', () => ({
  fetchHealth: vi.fn(),
}))

import { fetchHealth } from '@/shared/api/health'

const baseHealth = {
  status: 'ok',
  version: '0.1.0',
  pdfConversionAvailable: true,
}

describe('useAppStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('defaults to both modes available before loadFeatures resolves', () => {
    const store = useAppStore()
    expect(store.availableModes).toEqual(['rag', 'enrich'])
    expect(store.mode).toBe('rag')
    expect(store.featuresLoaded).toBe(false)
  })

  it('loadFeatures narrows availability to what /api/health reports', async () => {
    vi.mocked(fetchHealth).mockResolvedValueOnce({
      ...baseHealth,
      reasoningAvailable: true,
      enrichAvailable: false,
    })
    const store = useAppStore()
    await store.loadFeatures()
    expect(store.availability).toEqual({ rag: true, enrich: false })
    expect(store.availableModes).toEqual(['rag'])
    expect(store.featuresLoaded).toBe(true)
  })

  it('falls back to the first available mode when the current one disappears', async () => {
    // User has flipped to enrich before features load, then health says
    // only RAG is available → store auto-switches to RAG.
    vi.mocked(fetchHealth).mockResolvedValueOnce({
      ...baseHealth,
      reasoningAvailable: true,
      enrichAvailable: false,
    })
    const store = useAppStore()
    store.mode = 'enrich'
    await store.loadFeatures()
    expect(store.mode).toBe('rag')
  })

  it('leaves the current mode in place when it stays available', async () => {
    vi.mocked(fetchHealth).mockResolvedValueOnce({
      ...baseHealth,
      reasoningAvailable: true,
      enrichAvailable: true,
    })
    const store = useAppStore()
    store.mode = 'enrich'
    await store.loadFeatures()
    expect(store.mode).toBe('enrich')
  })

  it('keeps permissive defaults when fetchHealth throws', async () => {
    vi.mocked(fetchHealth).mockRejectedValueOnce(new Error('network down'))
    const store = useAppStore()
    await store.loadFeatures()
    // Both modes still considered available — better to let users see
    // every pill and let individual endpoints 503 than to hide modes
    // on a transient blip.
    expect(store.availableModes).toEqual(['rag', 'enrich'])
    expect(store.featuresLoaded).toBe(true)
  })

  it('setMode silently ignores attempts to switch to a disabled mode', async () => {
    vi.mocked(fetchHealth).mockResolvedValueOnce({
      ...baseHealth,
      reasoningAvailable: true,
      enrichAvailable: false,
    })
    const store = useAppStore()
    await store.loadFeatures()
    store.setMode('enrich')
    expect(store.mode).toBe('rag')
  })

  it('availableModes preserves canonical order regardless of availability shape', async () => {
    vi.mocked(fetchHealth).mockResolvedValueOnce({
      ...baseHealth,
      reasoningAvailable: false,
      enrichAvailable: true,
    })
    const store = useAppStore()
    await store.loadFeatures()
    expect(store.availableModes).toEqual(['enrich'])
  })
})
