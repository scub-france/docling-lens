import { apiFetch } from './http'

export interface HealthResponse {
  status: string
  version: string
  reasoningAvailable: boolean
  enrichAvailable: boolean
  pdfConversionAvailable: boolean
}

export function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/api/health')
}
