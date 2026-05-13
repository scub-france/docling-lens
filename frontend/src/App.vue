<script setup lang="ts">
/**
 * App root — picks the active feature page from `useAppStore.mode`.
 * The top-bar toggle (rendered inside each page's WorkspaceShell)
 * mutates that mode; this component just routes.
 */
import EnrichDebuggerPage from '@/features/enrich/ui/EnrichDebuggerPage.vue'
import RagDebuggerPage from '@/features/rag/ui/RagDebuggerPage.vue'
import { useAppStore } from '@/shared/stores/useAppStore'

const appStore = useAppStore()
</script>

<template>
  <RagDebuggerPage v-if="appStore.mode === 'rag'" />
  <EnrichDebuggerPage v-else-if="appStore.mode === 'enrich'" />
</template>
