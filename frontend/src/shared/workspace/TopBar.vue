<script setup lang="ts">
/**
 * Top bar — brand · current document · agent mode toggle · `New run`.
 *
 * The mode toggle is the only top-level switch in the app today: RAG
 * conversation vs. Enrich operations. Adding a third agent (extract,
 * write, edit) is one more entry in this template + a corresponding
 * page in `features/<mode>/`.
 */
import { computed } from 'vue'

import { useAppStore, type AppMode } from '@/shared/stores/useAppStore'
import { useDocumentStore } from '@/shared/stores/useDocumentStore'

const docStore = useDocumentStore()
const appStore = useAppStore()

const docLabel = computed(() => docStore.documentFilename ?? 'no document loaded')

interface ModeOption {
  value: AppMode
  label: string
}
// Display labels — the store's `availableModes` decides which entries
// actually render. Adding a new mode is two lines: one here + one in
// `AppMode` / `ALL_MODES` upstream.
const MODE_LABELS: Record<AppMode, string> = {
  rag: 'rag',
  enrich: 'enrich',
}

const visibleModes = computed<ModeOption[]>(() =>
  appStore.availableModes.map((m: AppMode) => ({ value: m, label: MODE_LABELS[m] })),
)

function onNewRun(): void {
  // The doc store owns the document; each feature decides for itself
  // whether to wipe its conversation/runs in reaction. Clearing the doc
  // also wipes focus state (handled by the store).
  docStore.clearDocument()
}
</script>

<template>
  <header class="topbar">
    <div class="brand">
      <span class="logo" aria-hidden="true">⌕</span>
      <span class="name">docling-lens</span>
    </div>
    <nav class="breadcrumbs" aria-label="Document">
      <span class="crumb">{{ docLabel }}</span>
    </nav>
    <!--
      Toggle is hidden when fewer than 2 modes are available — a single
      pill is just visual noise. Endpoints still 503 cleanly if anything
      hits a disabled agent regardless.
    -->
    <div v-if="visibleModes.length > 1" class="mode-toggle" role="tablist" aria-label="Agent mode">
      <button
        v-for="m in visibleModes"
        :key="m.value"
        role="tab"
        :aria-selected="appStore.mode === m.value"
        :class="{ active: appStore.mode === m.value }"
        @click="appStore.setMode(m.value)"
      >
        {{ m.label }}
      </button>
    </div>
    <span v-else-if="visibleModes.length === 1" class="mode-solo mono">
      {{ visibleModes[0].label }}
    </span>
    <div class="actions">
      <button class="primary" @click="onNewRun">
        <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path
            d="M8 3v10M3 8h10"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
          />
        </svg>
        New run
      </button>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  display: grid;
  /* brand · breadcrumb (flex grow) · mode toggle · actions */
  grid-template-columns: auto 1fr auto auto;
  align-items: center;
  gap: 18px;
  padding: 10px 18px;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}

.mode-toggle {
  display: flex;
  gap: 2px;
  background: var(--surface-2);
  border-radius: 6px;
  padding: 2px;
}
.mode-toggle button {
  font-family: var(--mono);
  font-size: 11px;
  border: none;
  background: transparent;
  color: var(--ink-3);
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  letter-spacing: 0.04em;
}
.mode-toggle button:hover {
  color: var(--ink);
}
.mode-toggle button.active {
  background: var(--surface);
  color: var(--ink);
  box-shadow: 0 1px 2px rgba(28, 27, 24, 0.06);
}
.mode-solo {
  font-size: 11px;
  letter-spacing: 0.04em;
  color: var(--ink-2);
  background: var(--surface-2);
  padding: 4px 10px;
  border-radius: 4px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
}
.logo {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  background: var(--accent);
  color: white;
  border-radius: 5px;
  font-size: 13px;
  box-shadow: 0 1px 0 rgba(28, 27, 24, 0.08);
}
.name {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: -0.01em;
  color: var(--ink);
}

.breadcrumbs {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: var(--ink-2);
}
.crumb {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--ink-2);
  background: var(--surface-2);
  border: 1px solid var(--border);
  padding: 3px 10px;
  border-radius: 999px;
}

.actions {
  display: flex;
  align-items: center;
}
/* `New run` — the only action up here, so it gets a clear primary
 * treatment: solid accent, subtle inner highlight + drop shadow, leading
 * `+` icon to match its semantics. */
.actions .primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  padding: 7px 14px 7px 12px;
  border-radius: 6px;
  background: var(--accent);
  border: 1px solid var(--accent);
  color: white;
  box-shadow:
    0 1px 2px rgba(28, 88, 60, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.14);
  transition:
    background 0.12s ease,
    border-color 0.12s ease,
    box-shadow 0.12s ease,
    transform 0.05s ease;
}
.actions .primary:hover {
  background: #1ab36e;
  border-color: #1ab36e;
  box-shadow:
    0 2px 6px rgba(28, 88, 60, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.18);
}
.actions .primary:active {
  background: #198a59;
  border-color: #198a59;
  transform: translateY(1px);
  box-shadow:
    0 1px 2px rgba(28, 88, 60, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}
.actions .primary svg {
  opacity: 0.9;
}
</style>
