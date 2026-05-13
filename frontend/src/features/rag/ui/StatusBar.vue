<script setup lang="ts">
/**
 * Footer status bar — mirrors the bottom strip from the maquette: run
 * status pill on the left, run summary in the middle, cost / model on the
 * right. Reads everything from the active turn so it stays in sync as the
 * user moves between conversation turns.
 */
import { computed } from 'vue'

import { useRagStore } from '../store'

const store = useRagStore()

const trace = computed(() => store.activeTurn?.trace ?? null)
const isPending = computed(
  () =>
    store.activeTurn !== null && store.activeTurn.trace === null && !store.activeTurn.errorMessage,
)
const statusLabel = computed(() => {
  if (!store.activeTurn) return 'Idle'
  if (store.activeTurn.errorMessage) return 'Failed'
  if (isPending.value) return 'Running'
  return 'Completed'
})
const statusKind = computed(() => {
  if (!store.activeTurn) return 'idle'
  if (store.activeTurn.errorMessage) return 'fail'
  if (isPending.value) return 'pending'
  return 'ok'
})

const stepCount = computed(() => trace.value?.steps.length ?? 0)
const citationCount = computed(() => {
  const t = trace.value
  if (!t) return 0
  const set = new Set<string>()
  for (const s of t.steps) for (const c of s.citations) set.add(c)
  return set.size
})
const durationLabel = computed(() => {
  const t = trace.value
  if (!t) return '—'
  return (t.totalDurationMs / 1000).toFixed(2) + 's'
})
const tokenLabel = computed(() => {
  const t = trace.value
  if (!t) return '—'
  return (t.tokensIn + t.tokensOut).toLocaleString()
})
const modelLabel = computed(() => trace.value?.modelId || 'agent')
</script>

<template>
  <footer class="statusbar mono">
    <span class="pill" :class="statusKind">● {{ statusLabel }}</span>
    <span v-if="store.activeTurn" class="meta">
      run {{ store.activeTurn.id }} · {{ stepCount }} steps · {{ citationCount }} citations ·
      {{ durationLabel }}
    </span>
    <span v-else class="meta">load a DoclingDocument to start a run</span>
    <span class="spacer" />
    <span v-if="trace" class="meta right"> {{ tokenLabel }} tokens · {{ modelLabel }} </span>
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
