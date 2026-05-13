<script setup lang="ts">
/**
 * App root — picks the active feature page from `useAppStore.mode`.
 *
 * On mount we fetch `/api/health` once to discover which agents are
 * actually wired server-side (per-agent feature flags). The store hides
 * the corresponding pills from the top-bar toggle; if the user's current
 * mode just became unavailable, the store falls back to the first
 * available one.
 *
 * Defaults are deliberately permissive — every mode is shown until the
 * fetch resolves — so a slow / failed `/api/health` doesn't blank the UI.
 */
import { onMounted } from 'vue'

import EnrichDebuggerPage from '@/features/enrich/ui/EnrichDebuggerPage.vue'
import RagDebuggerPage from '@/features/rag/ui/RagDebuggerPage.vue'
import { useAppStore } from '@/shared/stores/useAppStore'

const appStore = useAppStore()

onMounted(() => {
  void appStore.loadFeatures()
})
</script>

<template>
  <template v-if="appStore.availableModes.length === 0">
    <!-- Edge case: the backend exists but every agent flag is off.
         Surface it explicitly rather than silently showing a blank app. -->
    <div class="no-modes">
      <h1>docling-lens</h1>
      <p>
        No agent is enabled on the backend. Set <code>FEATURE_RAG</code> and/or
        <code>FEATURE_ENRICH</code> to <code>true</code> (and <code>REASONING_ENABLED=true</code>)
        to surface a workspace.
      </p>
    </div>
  </template>
  <RagDebuggerPage v-else-if="appStore.mode === 'rag'" />
  <EnrichDebuggerPage v-else-if="appStore.mode === 'enrich'" />
</template>

<style scoped>
.no-modes {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  text-align: center;
  padding: 24px;
}
.no-modes h1 {
  font-size: 18px;
  margin: 0 0 12px;
  color: var(--ink);
}
.no-modes p {
  font-size: 13px;
  color: var(--ink-2);
  max-width: 480px;
  line-height: 1.5;
}
.no-modes code {
  font-family: var(--mono);
  font-size: 12px;
  background: var(--surface-2);
  padding: 1px 5px;
  border-radius: 3px;
}
</style>
