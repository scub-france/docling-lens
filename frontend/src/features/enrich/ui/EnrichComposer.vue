<script setup lang="ts">
/**
 * Left pane of the Enrich workspace — what the conversation pane is for
 * RAG. The user picks one or more operations, optionally overrides the
 * model, hits Run. Past runs collapse into a chronological list below
 * the composer; clicking a run promotes it back to "active".
 */
import { computed } from 'vue'

import { useEnrichStore } from '../store'
import { ALL_ENRICH_OPERATIONS, type EnrichOperation, type EnrichRun } from '../types'
import { useDocumentStore } from '@/shared/stores/useDocumentStore'

const store = useEnrichStore()
const docStore = useDocumentStore()

const OP_LABELS: Record<EnrichOperation, string> = {
  summarize: 'Summarize',
  keywords: 'Keywords',
  entities: 'Entities',
}

// Honest per-op hints — only sections (with ≥100 chars subtree text),
// tables, and pictures get enriched. Paragraphs, list items, and
// captions are left untouched by docling-agent v0.1.0.
const OP_HINTS: Record<EnrichOperation, string> = {
  summarize: '2–3 sentence summary per section + table + picture',
  keywords: '3–7 search keywords per section + table + picture',
  entities: 'Named entities (PERSON, ORG, …) per section + table + picture',
}

const isPending = (r: EnrichRun): boolean => r.trace === null && r.errorMessage === null
const isRunning = computed(() => store.runs.some(isPending))

const canRun = computed(
  () => docStore.hasDocument && store.selectedOps.size > 0 && !isRunning.value,
)

function selectedCount(r: EnrichRun): number {
  return r.trace?.enrichments.length ?? 0
}

function fmtTime(ms: number): string {
  return new Date(ms).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

async function submit(): Promise<void> {
  if (!canRun.value) return
  await store.runWithSelected()
}
</script>

<template>
  <section class="pane composer">
    <header class="pane-head">
      <span class="label">ENRICH</span>
      <span v-if="store.activeRun" class="run-id mono">{{ store.activeRun.id }}</span>
    </header>

    <div class="scroll">
      <div class="ops-block">
        <p class="block-title">Operations</p>
        <label
          v-for="op in ALL_ENRICH_OPERATIONS"
          :key="op"
          class="op-row"
          :class="{ checked: store.selectedOps.has(op) }"
        >
          <input
            type="checkbox"
            :checked="store.selectedOps.has(op)"
            :disabled="isRunning"
            @change="store.toggleOp(op)"
          />
          <span class="op-text">
            <span class="op-name">{{ OP_LABELS[op] }}</span>
            <span class="op-hint">{{ OP_HINTS[op] }}</span>
          </span>
        </label>
      </div>

      <div class="model-block">
        <label class="block-title" for="enrich-model">Model</label>
        <input
          id="enrich-model"
          v-model="store.modelOverride"
          type="text"
          class="model-input mono"
          placeholder="agent default (e.g. mistral-small3.2)"
          :disabled="isRunning"
        />
      </div>

      <div v-if="store.runs.length > 0" class="history">
        <p class="block-title">History</p>
        <button
          v-for="r in store.runs"
          :key="r.id"
          type="button"
          class="run-card"
          :class="{
            active: r.id === store.activeRunId,
            pending: isPending(r),
            fail: !!r.errorMessage,
          }"
          @click="store.selectRun(r.id)"
        >
          <span class="run-head">
            <span class="run-time mono">{{ fmtTime(r.pendingAt) }}</span>
            <span class="run-status">
              <span v-if="isPending(r)">…running</span>
              <span v-else-if="r.errorMessage">failed</span>
              <span v-else>{{ selectedCount(r) }} enriched</span>
            </span>
          </span>
          <span class="run-ops mono">{{ r.operations.join(' · ') }}</span>
          <span v-if="r.errorMessage" class="run-error mono">{{ r.errorMessage }}</span>
        </button>
      </div>
    </div>

    <form class="footer" @submit.prevent="submit">
      <button type="submit" class="primary run-btn" :disabled="!canRun">
        {{
          isRunning
            ? 'Running…'
            : `Run ${store.selectedOps.size || 0} op${store.selectedOps.size === 1 ? '' : 's'} ↵`
        }}
      </button>
      <p v-if="!docStore.hasDocument" class="hint">Load a document in the right pane first.</p>
      <p v-else class="hint">
        Each op runs an extra LLM pass first to fix heading levels — expect 2–3× the raw enrichment
        time. The doc structure may also be rebuilt hierarchically by the agent.
      </p>
    </form>
  </section>
</template>

<style scoped>
.pane.composer {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg);
  min-width: 0;
}
.pane-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}
.label {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--ink-3);
  text-transform: uppercase;
}
.run-id {
  font-size: 12px;
  color: var(--ink-3);
}
.scroll {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.block-title {
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--ink-3);
  text-transform: uppercase;
  margin: 0 0 8px;
  display: block;
}

.ops-block {
  display: flex;
  flex-direction: column;
}
.op-row {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: start;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
}
.op-row:hover {
  background: var(--surface-2);
}
.op-row.checked {
  background: var(--accent-soft);
  border-color: rgba(30, 168, 113, 0.25);
}
.op-row input {
  margin-top: 3px;
  accent-color: var(--accent);
}
.op-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.op-name {
  font-size: 13px;
  color: var(--ink);
  font-weight: 500;
}
.op-row.checked .op-name {
  color: var(--accent);
}
.op-hint {
  font-size: 11px;
  color: var(--ink-3);
  line-height: 1.35;
}

.model-block {
  display: flex;
  flex-direction: column;
}
.model-input {
  font-size: 12px;
  padding: 6px 10px;
}

.history {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.run-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.12s ease,
    background 0.12s ease;
}
.run-card:hover {
  background: var(--surface-2);
}
.run-card.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.run-card.pending {
  border-style: dashed;
  border-color: #d6b955;
}
.run-card.fail {
  border-color: #f3b9ad;
  background: #fdf3f0;
}
.run-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 11px;
  color: var(--ink-3);
}
.run-time {
  color: var(--ink-2);
}
.run-status {
  font-size: 11px;
}
.run-ops {
  font-size: 11px;
  color: var(--ink-2);
}
.run-error {
  font-size: 11px;
  color: #87331f;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.footer {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-top: 1px solid var(--border);
  background: var(--surface);
  padding: 10px 14px;
}
.run-btn {
  width: 100%;
  font-family: var(--mono);
  font-size: 13px;
  padding: 8px 14px;
}
.hint {
  margin: 0;
  font-size: 11px;
  color: var(--ink-3);
}
</style>
