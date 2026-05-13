/**
 * `useDocumentStore` — single source of truth for the loaded document
 * and the current UI focus on it. Lives in `shared/` because it's used
 * by every feature (RAG conversation, enrich runs, future agents).
 *
 * Owns:
 *  - **Doc state**: filename / raw JSON / pre-parsed `DoclingDoc` / PDF
 *    blob / upload-conversion lifecycle.
 *  - **Focus state**: `focusedCitations` = the refs currently highlighted
 *    in the PDF + tree. Driven by whatever the user clicked last — a
 *    timeline step, a tree node, a future enrich item. Each setter bumps
 *    `focusTick` so consumers can re-fire scroll-into-view side effects
 *    even when the citations themselves didn't change.
 *
 * Per-feature state (RAG conversation turns, enrich operations, etc.)
 * stays in the feature's own Pinia store and reads from this one for
 * the doc + focus, never owns them.
 */

import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'

import { convertPdf } from '@/shared/api/documents'
import { parseDoc, type DoclingDoc } from '@/shared/docling/parseDoc'

export const useDocumentStore = defineStore('document', () => {
  /** Filename shown in the UI. Set on load/upload, null after `clearDocument`. */
  const documentFilename = ref<string | null>(null)
  /** Raw serialized DoclingDocument JSON — re-sent verbatim to agent runs. */
  const documentJson = ref<string | null>(null)
  /**
   * Original PDF bytes kept client-side so the PDF viewer can render
   * pages with bbox overlays. Null when the user loaded a bare JSON
   * trace (no PDF to render). `shallowRef` because a Blob is opaque
   * to Vue reactivity — deep-tracking would wrap it in a proxy and
   * break identity checks downstream.
   */
  const pdfBlob = shallowRef<Blob | null>(null)

  /** Parsed once per `documentJson` change, shared by every consumer. */
  const parsedDocument = computed<DoclingDoc | null>(() => parseDoc(documentJson.value))
  const hasDocument = computed(() => documentJson.value !== null)

  /** True while a PDF upload is being converted server-side. */
  const converting = ref(false)
  /** Last PDF-conversion error message, surfaced in the document pane. */
  const convertError = ref<string | null>(null)

  /**
   * Refs currently highlighted across all panes. Empty by default;
   * features call `setFocus` when their own selection changes (e.g.
   * RAG picks a step → focus = step.citations).
   */
  const focusedCitations = ref<string[]>([])
  /**
   * Bumps on every `setFocus` call — even when the citations are
   * unchanged. Watchers that need to re-scroll on every click listen
   * to this rather than `focusedCitations`, which would not refire on
   * same-value writes.
   */
  const focusTick = ref(0)

  function setFocus(citations: readonly string[]): void {
    focusedCitations.value = [...citations]
    focusTick.value += 1
  }

  function clearFocus(): void {
    focusedCitations.value = []
  }

  function loadDocument(filename: string, json: string, pdf: Blob | null = null): void {
    documentFilename.value = filename
    documentJson.value = json
    pdfBlob.value = pdf
    convertError.value = null
    clearFocus()
  }

  /**
   * Upload a PDF, ask the backend to convert it (Docling, in-process),
   * then stash the resulting `DoclingDocument` JSON + the original PDF
   * bytes so the viewer can render with bbox overlays.
   */
  async function uploadPdf(file: File): Promise<void> {
    converting.value = true
    convertError.value = null
    try {
      const res = await convertPdf(file)
      loadDocument(res.filename, res.documentJson, file)
    } catch (e) {
      convertError.value = e instanceof Error ? e.message : String(e)
    } finally {
      converting.value = false
    }
  }

  function clearDocument(): void {
    documentFilename.value = null
    documentJson.value = null
    pdfBlob.value = null
    convertError.value = null
    focusedCitations.value = []
    focusTick.value = 0
  }

  return {
    // state
    documentFilename,
    documentJson,
    pdfBlob,
    converting,
    convertError,
    focusedCitations,
    focusTick,
    // computed
    parsedDocument,
    hasDocument,
    // actions
    loadDocument,
    uploadPdf,
    clearDocument,
    setFocus,
    clearFocus,
  }
})
