import { apiFetch } from './http'

export interface ConvertResponse {
  filename: string
  documentJson: string
  sizeBytes: number
}

/**
 * Upload a PDF and get back the serialized `DoclingDocument` JSON.
 *
 * The backend delegates conversion to a docling-serve instance — runs
 * are several seconds per PDF. The returned JSON is held client-side in
 * `useDocumentStore` so subsequent agent runs (RAG, enrich, …) don't
 * re-pay the conversion cost.
 *
 * Errors (`ApiError.status`):
 *  - 503 when docling-serve isn't configured
 *  - 400 on non-PDF / empty upload
 *  - 413 when the file exceeds `MAX_PDF_SIZE_MB`
 *  - 500 on conversion failures
 */
export function convertPdf(file: File): Promise<ConvertResponse> {
  const form = new FormData()
  form.append('file', file)
  return apiFetch<ConvertResponse>('/api/documents', {
    method: 'POST',
    body: form,
  })
}
