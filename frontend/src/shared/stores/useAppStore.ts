/**
 * `useAppStore` — top-level UI mode for the debugger.
 *
 * Today the workspace can be in one of two modes: `rag` (DoclingRAGAgent
 * conversation) or `enrich` (DoclingEnrichingAgent operations). The
 * top bar exposes a toggle wired to this store; the App component picks
 * which feature page to mount based on the mode.
 *
 * Adding a third mode (extract, write, edit) is a one-line change here +
 * a matching feature page in `features/<mode>/`. The shared workspace
 * shell stays untouched.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

export type AppMode = 'rag' | 'enrich'

export const useAppStore = defineStore('app', () => {
  const mode = ref<AppMode>('rag')

  function setMode(next: AppMode): void {
    mode.value = next
  }

  return { mode, setMode }
})
