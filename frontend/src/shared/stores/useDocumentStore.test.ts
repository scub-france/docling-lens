import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDocumentStore } from './useDocumentStore'

vi.mock('@/shared/api/documents', () => ({
  convertPdf: vi.fn(),
}))

import { convertPdf } from '@/shared/api/documents'

describe('useDocumentStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loadDocument flips hasDocument and stores filename + json', () => {
    const store = useDocumentStore()
    expect(store.hasDocument).toBe(false)
    store.loadDocument('docling.json', '{"foo": 1}')
    expect(store.hasDocument).toBe(true)
    expect(store.documentFilename).toBe('docling.json')
    expect(store.documentJson).toBe('{"foo": 1}')
  })

  it('parsedDocument returns the parsed body on valid JSON', () => {
    const store = useDocumentStore()
    store.loadDocument('doc.json', '{"body": {"children": []}, "texts": [{"text": "hello"}]}')
    expect(store.parsedDocument).not.toBeNull()
    expect(store.parsedDocument?.body).toEqual({ children: [] })
    expect(store.parsedDocument?.texts).toEqual([{ text: 'hello' }])
  })

  it('parsedDocument is null on invalid JSON and after clearDocument', () => {
    const store = useDocumentStore()
    store.loadDocument('doc.json', 'not-json-at-all')
    expect(store.parsedDocument).toBeNull()
    store.loadDocument('doc.json', '{"body": {}}')
    expect(store.parsedDocument).not.toBeNull()
    store.clearDocument()
    expect(store.parsedDocument).toBeNull()
  })

  it('uploadPdf stores the converted document JSON, clears errors, exits converting', async () => {
    vi.mocked(convertPdf).mockResolvedValueOnce({
      filename: 'paper.pdf',
      documentJson: '{"name":"paper"}',
      sizeBytes: 12345,
    })
    const store = useDocumentStore()
    const file = new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], 'paper.pdf', {
      type: 'application/pdf',
    })

    await store.uploadPdf(file)

    expect(store.hasDocument).toBe(true)
    expect(store.documentFilename).toBe('paper.pdf')
    expect(store.documentJson).toBe('{"name":"paper"}')
    expect(store.pdfBlob).toBe(file)
    expect(store.convertError).toBeNull()
    expect(store.converting).toBe(false)
  })

  it('uploadPdf surfaces conversion errors and leaves the doc empty', async () => {
    vi.mocked(convertPdf).mockRejectedValueOnce(new Error('HTTP 503: not installed'))
    const store = useDocumentStore()
    const file = new File([new Uint8Array([1])], 'paper.pdf', { type: 'application/pdf' })

    await store.uploadPdf(file)

    expect(store.hasDocument).toBe(false)
    expect(store.convertError).toContain('503')
    expect(store.converting).toBe(false)
  })

  it('setFocus replaces citations and bumps focusTick on each call', () => {
    const store = useDocumentStore()
    expect(store.focusTick).toBe(0)
    store.setFocus(['#/texts/0'])
    expect(store.focusedCitations).toEqual(['#/texts/0'])
    expect(store.focusTick).toBe(1)
    // Re-setting the SAME citations still bumps the tick — that's the whole
    // point of the tick: it lets watchers refire on every click.
    store.setFocus(['#/texts/0'])
    expect(store.focusTick).toBe(2)
    store.setFocus(['#/texts/5', '#/texts/9'])
    expect(store.focusedCitations).toEqual(['#/texts/5', '#/texts/9'])
    expect(store.focusTick).toBe(3)
  })

  it('clearDocument wipes everything including focus state', () => {
    const store = useDocumentStore()
    store.loadDocument('doc.json', '{"body": {}}')
    store.setFocus(['#/texts/0'])
    store.clearDocument()
    expect(store.hasDocument).toBe(false)
    expect(store.pdfBlob).toBeNull()
    expect(store.focusedCitations).toEqual([])
    expect(store.focusTick).toBe(0)
    expect(store.convertError).toBeNull()
  })

  it('loadDocument resets focus so stale refs do not survive', () => {
    const store = useDocumentStore()
    store.loadDocument('a.json', '{}')
    store.setFocus(['#/texts/0'])
    store.loadDocument('b.json', '{}')
    expect(store.focusedCitations).toEqual([])
  })
})
