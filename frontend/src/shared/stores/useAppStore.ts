/**
 * `useAppStore` — top-level UI mode for the debugger.
 *
 * Today the workspace can be in one of two modes: `rag` or `enrich`.
 * Which modes are actually available is discovered on boot from
 * `/api/health` — the backend's per-agent feature flags decide which
 * runners are wired, and the frontend hides the corresponding pills
 * from the top bar.
 *
 * Adding a third mode (extract, write, edit) is a one-line change to
 * `AppMode` + a matching feature page + a flag on the backend. The
 * shared workspace shell stays untouched.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { fetchHealth } from '@/shared/api/health'

export type AppMode = 'rag' | 'enrich'

/** Canonical order shown in the top-bar toggle. */
export const ALL_MODES: readonly AppMode[] = ['rag', 'enrich'] as const

/** Default availability — used before `/api/health` resolves and as a
 *  safe fallback when the call fails. ON for every mode so the UI is
 *  not silently empty on a network blip. */
const DEFAULT_AVAILABILITY: Readonly<Record<AppMode, boolean>> = {
  rag: true,
  enrich: true,
}

export const useAppStore = defineStore('app', () => {
  const mode = ref<AppMode>('rag')

  /** Per-mode availability discovered from the backend. */
  const availability = ref<Record<AppMode, boolean>>({ ...DEFAULT_AVAILABILITY })

  /** `true` once `loadFeatures` has at least attempted a fetch — lets
   *  the UI distinguish "still booting" from "loaded but no modes". */
  const featuresLoaded = ref(false)

  const availableModes = computed<AppMode[]>(() => ALL_MODES.filter((m) => availability.value[m]))

  function setMode(next: AppMode): void {
    // Silently ignore attempts to switch to a disabled mode.
    if (!availability.value[next]) return
    mode.value = next
  }

  /**
   * Discover which agents are wired server-side. Single-shot at boot;
   * the backend wire-up is static (env-driven), so polling buys nothing.
   * On error we leave the defaults in place — better to show every pill
   * and let individual endpoints 503 than to silently hide modes on a
   * transient network failure.
   */
  async function loadFeatures(): Promise<void> {
    try {
      const health = await fetchHealth()
      availability.value = {
        rag: health.reasoningAvailable,
        enrich: health.enrichAvailable,
      }
      // If the current mode just became unavailable (e.g. the user
      // bookmarked an old state, or the backend toggled overnight),
      // fall back to the first available mode.
      if (!availability.value[mode.value] && availableModes.value.length > 0) {
        mode.value = availableModes.value[0]
      }
    } catch {
      // Keep defaults — see the doc comment above.
    } finally {
      featuresLoaded.value = true
    }
  }

  return {
    mode,
    availability,
    availableModes,
    featuresLoaded,
    setMode,
    loadFeatures,
  }
})
