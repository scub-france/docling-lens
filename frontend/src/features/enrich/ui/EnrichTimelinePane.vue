<script setup lang="ts">
/**
 * Center pane of the Enrich workspace — vertical list of enrichments
 * grouped by operation. Each row is the (selfRef, operation, value)
 * triple from the active run's trace. Clicking a row calls
 * `store.focusEnrichment` which propagates the ref to the shared doc
 * store; the right pane scrolls to the matching node, and the (always
 * mounted) PDF section below highlights the bbox.
 *
 * The PDF below this pane mirrors the RAG view — same `<PdfViewer>`
 * lazy-loaded from shared, driven by `docStore.focusedCitations`.
 */
import { computed, defineAsyncComponent } from 'vue'

import { useEnrichStore } from '../store'
import { ALL_ENRICH_OPERATIONS, type EnrichOperation, type NodeEnrichment } from '../types'
import { useDocumentStore } from '@/shared/stores/useDocumentStore'

const PdfViewer = defineAsyncComponent(() => import('@/shared/workspace/PdfViewer.vue'))

const store = useEnrichStore()
const docStore = useDocumentStore()

const OP_LABELS: Record<EnrichOperation, string> = {
  summarize: 'SUMMARIZE',
  keywords: 'KEYWORDS',
  entities: 'ENTITIES',
}

const OP_ACCENT: Record<EnrichOperation, string> = {
  summarize: 'green',
  keywords: 'blue',
  entities: 'purple',
}

interface OpGroup {
  op: EnrichOperation
  items: NodeEnrichment[]
}

const grouped = computed<OpGroup[]>(() => {
  const by = new Map<EnrichOperation, NodeEnrichment[]>()
  for (const e of store.activeEnrichments) {
    const list = by.get(e.operation) ?? []
    list.push(e)
    by.set(e.operation, list)
  }
  // Canonical order: same as `ALL_ENRICH_OPERATIONS`.
  return ALL_ENRICH_OPERATIONS.filter((op) => by.has(op)).map((op) => ({
    op,
    items: by.get(op) ?? [],
  }))
})

const focused = computed<Set<string>>(() => new Set(docStore.focusedCitations))

const trace = computed(() => store.activeRun?.trace ?? null)
const header = computed(() => {
  const t = trace.value
  if (!t) return { count: 0, ops: 0, duration: '—' }
  return {
    count: t.enrichments.length,
    ops: t.operations.length,
    duration: (t.totalDurationMs / 1000).toFixed(2) + 's',
  }
})

interface EntityShape {
  entity_type?: unknown
  mention?: unknown
}

function isEntity(x: unknown): x is EntityShape {
  return typeof x === 'object' && x !== null && ('entity_type' in x || 'mention' in x)
}

/**
 * Per-op value renderer.
 *  - summarize → the string verbatim
 *  - keywords  → comma-joined list[str]
 *  - entities  → "mention (TYPE), …" where `mention` and `entity_type`
 *                come from docling-agent's `_generate_entities` contract.
 *                Falls back to JSON.stringify on individual items the
 *                model produced in an unexpected shape so the row never
 *                ends up empty.
 */
function renderValue(e: NodeEnrichment): string {
  const v = e.value
  if (v == null) return '—'
  if (e.operation === 'entities' && Array.isArray(v)) {
    return v
      .map((x) => {
        if (isEntity(x)) {
          const mention = typeof x.mention === 'string' ? x.mention : ''
          const type = typeof x.entity_type === 'string' ? x.entity_type : ''
          if (mention && type) return `${mention} (${type})`
          return mention || type || JSON.stringify(x)
        }
        return typeof x === 'string' ? x : JSON.stringify(x)
      })
      .join(', ')
  }
  if (typeof v === 'string') return v
  if (Array.isArray(v)) {
    return v.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(', ')
  }
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

function onClick(e: NodeEnrichment): void {
  store.focusEnrichment(e)
}
</script>

<template>
  <section class="pane trace">
    <header class="pane-head">
      <span class="label">ENRICHMENTS</span>
      <span v-if="trace" class="meta mono">
        {{ header.count }} items · {{ header.ops }} ops · {{ header.duration }}
      </span>
    </header>

    <div class="trace-section">
      <div v-if="!trace && !store.activeRun" class="empty">
        <p>
          No enrichments yet. Pick one or more operations in the composer pane and click
          <strong>Run</strong> to start.
        </p>
      </div>
      <div v-else-if="!trace && store.activeRun" class="empty">
        <p>Running enrichments — this can take a moment per item × op combination.</p>
      </div>
      <div v-else-if="grouped.length === 0" class="empty">
        <p>The run completed but produced no enrichments. The model may have skipped every item.</p>
      </div>

      <div v-else class="groups">
        <div v-for="g in grouped" :key="g.op" class="group" :class="[`accent-${OP_ACCENT[g.op]}`]">
          <header class="group-head">
            <span class="group-tag mono">{{ OP_LABELS[g.op] }}</span>
            <span class="group-count mono">{{ g.items.length }}</span>
          </header>
          <ul class="items">
            <li
              v-for="item in g.items"
              :key="`${g.op}:${item.selfRef}`"
              class="item"
              :class="{ active: focused.has(item.selfRef) }"
              :title="item.selfRef"
              @click="onClick(item)"
            >
              <span class="item-ref mono">{{ item.selfRef }}</span>
              <span class="item-value">{{ renderValue(item) }}</span>
            </li>
          </ul>
        </div>
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
          :active-citations="docStore.focusedCitations"
          :focus-tick="docStore.focusTick"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.pane.trace {
  display: grid;
  grid-template-rows: auto auto 1fr;
  border-right: 1px solid var(--border);
  background: var(--bg);
}
.pane-head {
  display: grid;
  grid-template-columns: auto 1fr;
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

.trace-section {
  overflow-y: auto;
  padding: 12px 14px;
  min-height: 0;
  max-height: 50vh;
}
.empty {
  color: var(--ink-3);
  font-size: 13px;
  text-align: center;
  padding: 24px;
}
.empty strong {
  color: var(--ink-2);
}

.groups {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 4px;
}
.group-tag {
  font-size: 10px;
  letter-spacing: 0.06em;
  padding: 1px 8px;
  border-radius: 3px;
  font-weight: 600;
  background: var(--surface-2);
  color: var(--ink-3);
  border: 1px solid var(--border);
}
.group.accent-green .group-tag {
  color: var(--accent);
  background: var(--accent-soft);
  border-color: #b9e3cf;
}
.group.accent-blue .group-tag {
  color: #1763c2;
  background: #ecf4fc;
  border-color: #c8defa;
}
.group.accent-purple .group-tag {
  color: #5a32c0;
  background: #efe9fb;
  border-color: #d6c8f1;
}
.group.accent-amber .group-tag {
  color: #a35d12;
  background: #fbe9d4;
  border-color: #ecc89f;
}
.group-count {
  font-size: 10px;
  color: var(--ink-3);
}

.items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.item {
  display: grid;
  grid-template-columns: 110px 1fr;
  align-items: baseline;
  gap: 10px;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  border-left: 2px solid transparent;
  font-size: 12.5px;
}
.item:hover {
  background: var(--surface-2);
}
.item.active {
  background: var(--citation);
  border-left-color: var(--citation-strong);
}
.item-ref {
  font-size: 11px;
  color: var(--ink-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.item.active .item-ref {
  color: #5b4500;
}
.item-value {
  font-family: var(--serif);
  font-size: 13px;
  color: var(--ink);
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
