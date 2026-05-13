<script setup lang="ts">
/**
 * RAG debugger page — assembles the shared `WorkspaceShell` with RAG-
 * specific panes (conversation + timeline) and the shared `DocumentPane`.
 * The shell owns the layout (top bar, 3-column body, status bar);
 * everything inside the slots is feature-specific.
 */
import ConversationPane from './ConversationPane.vue'
import ReasoningTracePane from './ReasoningTracePane.vue'
import StatusBar from './StatusBar.vue'
import DocumentPane from '@/shared/workspace/DocumentPane.vue'
import WorkspaceShell from '@/shared/workspace/WorkspaceShell.vue'
</script>

<template>
  <WorkspaceShell>
    <template #left-pane>
      <ConversationPane />
    </template>
    <template #center-pane>
      <ReasoningTracePane />
    </template>
    <template #right-pane>
      <DocumentPane />
    </template>
    <template #status-bar>
      <StatusBar />
    </template>
  </WorkspaceShell>
</template>
