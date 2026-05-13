<script setup lang="ts">
/**
 * `WorkspaceShell` — pure layout shell for an agent debugger page.
 *
 * Provides the 100vh grid (top bar / 3-column body / status bar) and
 * leaves every cell as a named slot. Each feature (`rag`, future
 * `enrich`) assembles the shell with its own panes — the shell itself
 * is feature-agnostic.
 *
 * Slots:
 *   - `top-bar`       (auto-mounts `<TopBar />` when not provided)
 *   - `left-pane`     (e.g. RAG conversation, enrich composer)
 *   - `center-pane`   (e.g. RAG trace + PDF, enrich timeline)
 *   - `right-pane`    (typically `<DocumentPane />`)
 *   - `status-bar`    (feature-specific)
 */
import TopBar from './TopBar.vue'
</script>

<template>
  <div class="page">
    <slot name="top-bar">
      <TopBar />
    </slot>
    <div class="body">
      <slot name="left-pane" />
      <slot name="center-pane" />
      <slot name="right-pane" />
    </div>
    <slot name="status-bar" />
  </div>
</template>

<style scoped>
.page {
  height: 100vh;
  display: grid;
  grid-template-rows: auto 1fr auto;
  background: var(--bg);
}
.body {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(360px, 1fr) minmax(320px, 480px);
  min-height: 0;
}
</style>
