<script setup lang="ts">
/**
 * Left pane — conversation log + composer. Each turn shows the user query
 * and the agent's final answer (or pending / error state). Clicking a turn
 * makes it active so the trace pane reflects that run.
 *
 * The answer is rendered as plain text (`{{ trace.answer }}`) — never as
 * HTML. If we ever surface markdown or inline citation chips here, install
 * a sanitizer (DOMPurify) and renderer (marked) again — they were removed
 * once the plain-text contract stabilized.
 */
import { computed, nextTick, ref, watch } from 'vue'

import { useRagStore } from '../store'
import type { ConversationTurn } from '../types'
import { useDocumentStore } from '@/shared/stores/useDocumentStore'

const store = useRagStore()
const docStore = useDocumentStore()
const composer = ref('')
const submitting = ref(false)
const scroller = ref<HTMLElement | null>(null)

const turns = computed<ConversationTurn[]>(() => store.turns)

watch(
  () => turns.value.length,
  async () => {
    await nextTick()
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  },
)

async function submit(): Promise<void> {
  if (!composer.value.trim() || submitting.value || !docStore.hasDocument) return
  submitting.value = true
  const text = composer.value
  composer.value = ''
  try {
    await store.askQuestion(text)
  } finally {
    submitting.value = false
  }
}

function isPending(t: ConversationTurn): boolean {
  return t.trace === null && t.errorMessage === null
}

function selectTurn(t: ConversationTurn): void {
  if (t.trace && t.trace.steps.length > 0) {
    store.selectStep(t.id, t.trace.steps[0].id)
  } else {
    store.selectStep(t.id, null)
  }
}

function formatTime(ms: number): string {
  const d = new Date(ms)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
</script>

<template>
  <section class="pane conversation">
    <header class="pane-head">
      <span class="label">CONVERSATION</span>
      <span class="run-id mono">{{ store.activeTurn?.id ?? '—' }}</span>
    </header>

    <div ref="scroller" class="scroll">
      <div v-if="turns.length === 0" class="empty">
        <p>
          Load a <code>DoclingDocument</code> JSON in the right pane, then ask a question to start
          inspecting the agent.
        </p>
      </div>
      <ol class="turns">
        <li
          v-for="t in turns"
          :key="t.id"
          class="turn"
          :class="{ active: t.id === store.activeTurnId }"
          @click="selectTurn(t)"
        >
          <div class="msg user">
            <div class="meta">
              <span class="role">you</span>
              <span class="time mono">{{ formatTime(t.pendingAt) }}</span>
            </div>
            <p class="body">
              {{ t.query }}
            </p>
          </div>

          <div class="msg agent">
            <div class="meta">
              <span
                class="bullet"
                :class="{ ok: t.trace?.converged, pending: isPending(t), fail: !!t.errorMessage }"
                >●</span
              >
              <span class="time mono">{{ formatTime(t.pendingAt) }}</span>
              <span v-if="t.trace" class="stats">
                {{ t.trace.steps.length }} steps ·
                {{ (t.trace.totalDurationMs / 1000).toFixed(2) }}s
              </span>
            </div>
            <p v-if="isPending(t)" class="body pending">Thinking…</p>
            <p v-else-if="t.errorMessage" class="body fail">
              {{ t.errorMessage }}
            </p>
            <p v-else-if="t.trace" class="body">
              {{ t.trace.answer }}
            </p>
            <div v-if="t.trace" class="footnote mono">
              {{ t.trace.tokensIn }} in · {{ t.trace.tokensOut }} out ·
              {{ (t.trace.totalDurationMs / 1000).toFixed(2) }}s
            </div>
          </div>
        </li>
      </ol>
    </div>

    <form class="composer" @submit.prevent="submit">
      <input
        v-model="composer"
        type="text"
        placeholder="Ask a follow-up…"
        :disabled="!docStore.hasDocument || submitting"
      />
      <!--
        Per-run model override. Empty falls back to the backend's
        `REASONING_MODEL_ID` env (Ollama model id, e.g. `mistral-small3.2`).
        The store carries it through `askQuestion` → `runReasoning({ modelId })`.
      -->
      <div class="composer-row">
        <span class="model-label mono">model</span>
        <input
          v-model="store.modelOverride"
          type="text"
          class="model-input mono"
          placeholder="agent default (e.g. mistral-small3.2)"
          :disabled="submitting"
        />
      </div>
      <div class="composer-meta">
        <span class="mono ink-3">{{ store.modelOverride || 'agent default' }}</span>
        <button
          type="submit"
          class="primary run-btn"
          :disabled="!docStore.hasDocument || submitting || !composer.trim()"
        >
          {{ submitting ? 'Running…' : 'Run ↵' }}
        </button>
      </div>
    </form>
  </section>
</template>

<style scoped>
.pane.conversation {
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
  padding: 12px 14px;
}
.empty {
  color: var(--ink-3);
  font-size: 13px;
  padding: 16px 0;
}
.empty code {
  font-family: var(--mono);
  font-size: 12px;
  background: var(--surface-2);
  padding: 1px 4px;
  border-radius: 3px;
}
.turns {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.turn {
  cursor: pointer;
  padding: 8px;
  border-radius: var(--radius);
  border: 1px solid transparent;
  transition:
    border-color 0.12s ease,
    background 0.12s ease;
}
.turn:hover {
  background: var(--surface-2);
}
.turn.active {
  border-color: var(--border-strong);
  background: var(--surface);
}
.msg {
  margin-bottom: 8px;
}
.msg:last-child {
  margin-bottom: 0;
}
.msg .meta {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 11px;
  color: var(--ink-3);
  margin-bottom: 4px;
}
.role {
  background: var(--surface-2);
  color: var(--ink-2);
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
}
.bullet.ok {
  color: var(--accent);
}
.bullet.pending {
  color: #b58000;
}
.bullet.fail {
  color: #c0392b;
}
.body {
  margin: 0;
  font-family: var(--serif);
  font-size: 15px;
  line-height: 1.5;
  color: var(--ink);
}
.body.pending {
  color: var(--ink-3);
  font-style: italic;
}
.body.fail {
  color: #c0392b;
  font-family: var(--mono);
  font-size: 12px;
}
.stats {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 11px;
}
.footnote {
  margin-top: 6px;
  font-size: 11px;
  color: var(--ink-3);
}
.composer {
  border-top: 1px solid var(--border);
  padding: 10px 14px;
  background: var(--surface);
}
.composer > input {
  width: 100%;
}
.composer-row {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.model-label {
  font-size: 10px;
  letter-spacing: 0.06em;
  color: var(--ink-3);
  text-transform: uppercase;
}
.model-input {
  width: 100%;
  font-size: 12px;
  padding: 4px 8px;
}
.run-btn {
  font-size: 12px;
  padding: 5px 14px;
  font-family: var(--mono);
}
.composer-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
  font-size: 11px;
}
.ink-3 {
  color: var(--ink-3);
}
</style>
