<script setup lang="ts">
/**
 * Middle pane — split vertically:
 *   - Top: trace view (timeline Gantt, or graph placeholder)
 *   - Bottom: PDF viewer with bbox overlays
 *
 * Both views are mounted at once so clicking a step in the timeline scrolls
 * the PDF (and the right document pane) to the matching citation, with no
 * tab to flip. The inspector popup is intentionally not mounted here — the
 * inspector callout was getting in the way of the trace; it can come back
 * as a dedicated drawer later if needed.
 */
import { computed, defineAsyncComponent, ref } from 'vue'

import { useRagStore } from '../store'
import TimelineGantt from './TimelineGantt.vue'
import { useDocumentStore } from '@/shared/stores/useDocumentStore'

// PDF.js is heavy (~370 KB minified). Lazy-load so the initial bundle
// stays small until the user actually has a PDF on screen.
const PdfViewer = defineAsyncComponent(() => import('@/shared/workspace/PdfViewer.vue'))

const store = useRagStore()
const docStore = useDocumentStore()

type View = 'graph' | 'timeline'
const view = ref<View>('timeline')

const focusedCitations = computed<string[]>(() => docStore.focusedCitations)

const trace = computed(() => store.activeTurn?.trace ?? null)
const header = computed(() => {
  const t = trace.value
  if (!t) return { count: 0, duration: '—' }
  return {
    count: t.steps.length,
    duration: (t.totalDurationMs / 1000).toFixed(2) + 's',
  }
})

function onSelect(stepId: string): void {
  if (!store.activeTurn) return
  store.selectStep(store.activeTurn.id, stepId)
}
</script>

<template>
  <section class="pane trace">
    <header class="pane-head">
      <span class="label">REASONING TRACE</span>
      <span v-if="trace" class="meta mono"> {{ header.count }} steps · {{ header.duration }} </span>
      <div class="tabs">
        <button :class="{ active: view === 'graph' }" @click="view = 'graph'">graph</button>
        <button :class="{ active: view === 'timeline' }" @click="view = 'timeline'">
          timeline
        </button>
        <button class="icon" title="Refresh">↻</button>
      </div>
    </header>

    <div class="trace-section">
      <div v-if="!trace" class="empty">
        <p>No trace yet. Ask a question in the conversation pane to start a run.</p>
      </div>
      <TimelineGantt
        v-else-if="view === 'timeline'"
        :trace="trace"
        :active-step-id="store.activeStepId"
        @select="onSelect"
      />
      <div v-else class="placeholder">
        <p>Graph view coming soon — switch to <em>timeline</em> for now.</p>
      </div>
    </div>

    <div class="pdf-section">
      <div class="section-head">
        <span class="label">PDF</span>
        <span v-if="docStore.documentFilename" class="meta mono">{{
          docStore.documentFilename
        }}</span>
      </div>
      <div class="pdf-scroll">
        <PdfViewer
          :pdf-blob="docStore.pdfBlob"
          :parsed-document="docStore.parsedDocument"
          :active-citations="focusedCitations"
          :focus-tick="docStore.focusTick"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.pane.trace {
  display: grid;
  /* Header / trace section / pdf section. The trace sizes to its content
   * (timeline rows + axis are compact) and the PDF reclaims everything
   * else. `max-height` on the trace caps it so a 100-step run can scroll
   * internally instead of pushing the PDF off-screen. */
  grid-template-rows: auto auto 1fr;
  border-right: 1px solid var(--border);
  background: var(--bg);
}
.pane-head {
  display: grid;
  grid-template-columns: auto auto 1fr;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}
.label {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--ink-3);
  text-transform: uppercase;
}
.meta {
  color: var(--ink-3);
  font-size: 12px;
}
.tabs {
  display: flex;
  gap: 4px;
  justify-self: end;
}
.tabs button {
  padding: 3px 8px;
  font-size: 11px;
  font-family: var(--mono);
  color: var(--ink-3);
}
.tabs button.active {
  color: var(--ink);
  background: var(--surface-2);
  border-color: var(--border-strong);
}
.tabs button.icon {
  font-family: var(--sans);
}

.trace-section {
  overflow-y: auto;
  padding: 14px;
  min-height: 0;
  max-height: 50vh;
}
.empty,
.placeholder {
  color: var(--ink-3);
  font-size: 13px;
  text-align: center;
  padding: 24px;
}

.pdf-section {
  display: grid;
  grid-template-rows: auto 1fr;
  border-top: 1px solid var(--border);
  background: var(--surface-2);
  min-height: 0;
}
.section-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}
.pdf-scroll {
  overflow-y: auto;
  min-height: 0;
}
</style>
