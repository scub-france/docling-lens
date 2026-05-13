<script setup lang="ts">
/**
 * Footer status bar for the enrich workspace — mirrors the RAG one but
 * reads from the enrich store: status pill, run id + ops + count, model
 * label on the right.
 */
import { computed } from 'vue'

import { useEnrichStore } from '../store'

const store = useEnrichStore()

const trace = computed(() => store.activeRun?.trace ?? null)
const isPending = computed(
  () => store.activeRun !== null && store.activeRun.trace === null && !store.activeRun.errorMessage,
)
const statusLabel = computed(() => {
  if (!store.activeRun) return 'Idle'
  if (store.activeRun.errorMessage) return 'Failed'
  if (isPending.value) return 'Running'
  return 'Completed'
})
const statusKind = computed(() => {
  if (!store.activeRun) return 'idle'
  if (store.activeRun.errorMessage) return 'fail'
  if (isPending.value) return 'pending'
  return 'ok'
})

const itemCount = computed(() => trace.value?.enrichments.length ?? 0)
const durationLabel = computed(() => {
  const t = trace.value
  if (!t) return '—'
  return (t.totalDurationMs / 1000).toFixed(2) + 's'
})
const modelLabel = computed(() => trace.value?.modelId || 'agent')
const opsLabel = computed(() => trace.value?.operations.join(' · ') ?? '')
</script>

<template>
  <footer class="statusbar mono">
    <span class="pill" :class="statusKind">● {{ statusLabel }}</span>
    <span v-if="store.activeRun" class="meta">
      run {{ store.activeRun.id }} · {{ itemCount }} enrichments ·
      {{ durationLabel }}
    </span>
    <span v-else class="meta">pick operations and Run to start enriching</span>
    <span class="spacer" />
    <span v-if="opsLabel" class="meta right">{{ opsLabel }} · {{ modelLabel }}</span>
  </footer>
</template>

<style scoped>
.statusbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg);
  color: var(--ink-2);
  font-size: 12px;
}
.spacer {
  flex: 1;
}
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  font-size: 11px;
}
.pill.ok {
  color: var(--accent);
}
.pill.pending {
  color: #b58000;
}
.pill.fail {
  color: #c0392b;
}
.right {
  color: var(--ink-3);
}
</style>
