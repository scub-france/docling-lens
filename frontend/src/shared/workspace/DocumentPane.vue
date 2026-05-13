<script setup lang="ts">
/**
 * Right pane — DoclingDocument structure browser.
 *
 * Two view modes:
 *  - "tree": faithful walk of `body.children` exposed by `useDocTree`.
 *    Each item is shown at the real depth produced by docling; if a
 *    `section_header` has paragraphs as `children`, they appear nested,
 *    otherwise they appear flat. No synthetic re-parenting.
 *  - "by-type": inventory view grouped by collection bucket (Sections /
 *    Paragraphs / Tables / Pictures / …). Mirrors Docling Studio's view.
 *
 * Clicks call `docStore.setFocus([ref])`, which highlights the matching
 * bbox in the PDF and the matching node here. The reverse direction is
 * wired in the focus watcher: a timeline-driven `focusTick` bump auto-
 * uncollapses ancestors and scrolls the first focused ref into view.
 */
import { computed, nextTick, ref, watch } from 'vue'

import type { DocNode } from '@/shared/docling/useDocTree'
import { useDocTree } from '@/shared/docling/useDocTree'
import { useDocumentStore } from '@/shared/stores/useDocumentStore'
import { NO_DECORATIONS, type DecorationsMap, type NodeDecoration } from './decorations'

const props = withDefaults(
  defineProps<{
    /**
     * Per-`self_ref` visual hints to render alongside each node. Features
     * (enrich, future agents) compute this map from their own state and
     * pass it down — the pane is feature-agnostic.
     */
    decorations?: DecorationsMap
  }>(),
  { decorations: () => NO_DECORATIONS },
)

const docStore = useDocumentStore()
const fileInput = ref<HTMLInputElement | null>(null)
const parseError = ref<string | null>(null)
const scroller = ref<HTMLElement | null>(null)
const filter = ref('')

function decorationsFor(ref: string): readonly NodeDecoration[] {
  return props.decorations.get(ref) ?? []
}

type ViewMode = 'tree' | 'by-type'
const view = ref<ViewMode>('tree')

const doc = computed(() => docStore.parsedDocument)
const tree = useDocTree(doc, filter)

const totalCount = computed(() => tree.allNodes.value.length)

/* ---------- By-type view: inventory grouped by collection bucket ---------- */

const SECTIONS_KINDS = new Set(['section_header', 'title', 'page_header'])
const PARAGRAPH_KINDS = new Set(['text', 'paragraph', 'list_item', 'caption', 'footnote'])

function bucketOf(kind: string): string {
  if (SECTIONS_KINDS.has(kind)) return 'sections'
  if (kind === 'table') return 'tables'
  if (kind === 'picture') return 'pictures'
  if (PARAGRAPH_KINDS.has(kind)) return 'paragraphs'
  if (kind === 'code' || kind === 'formula') return 'code'
  if (kind.startsWith('group')) return 'groups'
  return 'other'
}

interface BucketDescriptor {
  key: string
  label: string
}
// Single source of truth for the four-bucket order + labels + defaults —
// adding a bucket here lights up the inventory view without further edits.
const BUCKETS: BucketDescriptor[] = [
  { key: 'sections', label: 'Sections' },
  { key: 'paragraphs', label: 'Paragraphs' },
  { key: 'tables', label: 'Tables' },
  { key: 'pictures', label: 'Pictures' },
  { key: 'code', label: 'Code & formulas' },
  { key: 'groups', label: 'Groups' },
  { key: 'other', label: 'Other' },
]
const DEFAULT_OPEN_BUCKETS = new Set(['sections', 'paragraphs', 'tables', 'pictures'])

interface Bucket extends BucketDescriptor {
  nodes: DocNode[]
}

const byTypeBuckets = computed<Bucket[]>(() => {
  const by = new Map<string, DocNode[]>()
  // The visible-set computation is reused here so filter behavior stays
  // identical between tree and inventory views. Depth is flattened to 0
  // because hierarchy is not the question in an inventory.
  for (const n of tree.visibleNodes.value) {
    const b = bucketOf(n.kind)
    const list = by.get(b) ?? []
    list.push({ ...n, depth: 0 })
    by.set(b, list)
  }
  return BUCKETS.filter((b) => by.has(b.key)).map((b) => ({ ...b, nodes: by.get(b.key) ?? [] }))
})

const bucketCollapsed = ref<Record<string, boolean>>({})
function toggleBucket(b: Bucket): void {
  bucketCollapsed.value = { ...bucketCollapsed.value, [b.key]: !isBucketExpanded(b) }
}
function isBucketExpanded(b: Bucket): boolean {
  if (b.key in bucketCollapsed.value) return !bucketCollapsed.value[b.key]
  return DEFAULT_OPEN_BUCKETS.has(b.key)
}

/* ---------- Expand-all / collapse-all (scoped to current view) ---------- */

function expandAll(): void {
  if (view.value === 'tree') {
    tree.expandAll()
  } else {
    const next: Record<string, boolean> = {}
    for (const b of byTypeBuckets.value) next[b.key] = false
    bucketCollapsed.value = next
  }
}

function collapseAll(): void {
  if (view.value === 'tree') {
    tree.collapseAll()
  } else {
    const next: Record<string, boolean> = {}
    for (const b of byTypeBuckets.value) next[b.key] = true
    bucketCollapsed.value = next
  }
}

/* ---------- Focus sync (timeline → tree) ---------- */

const focused = computed<Set<string>>(() => new Set(docStore.focusedCitations))

watch(
  () => docStore.focusTick,
  async () => {
    if (focused.value.size === 0) return
    tree.uncollapseAncestors(focused.value)
    if (view.value === 'by-type') {
      const next = { ...bucketCollapsed.value }
      for (const focusRefStr of focused.value) {
        const node = tree.allNodes.value.find((n) => n.ref === focusRefStr)
        if (node) next[bucketOf(node.kind)] = false
      }
      bucketCollapsed.value = next
    }
    await nextTick()
    if (!scroller.value) return
    const first = focused.value.values().next().value
    if (!first) return
    const el = scroller.value.querySelector<HTMLElement>(`[data-ref="${CSS.escape(first)}"]`)
    if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' })
  },
)

/* ---------- File handling ---------- */

function pickFile(): void {
  fileInput.value?.click()
}
function isPdf(file: File): boolean {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
}
async function onFile(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  parseError.value = null
  try {
    if (isPdf(file)) {
      await docStore.uploadPdf(file)
    } else {
      const text = await file.text()
      JSON.parse(text)
      docStore.loadDocument(file.name, text)
    }
  } catch (e) {
    parseError.value = e instanceof Error ? e.message : 'Invalid file'
  } finally {
    input.value = ''
  }
}

function onNodeClick(n: DocNode): void {
  docStore.setFocus([n.ref])
}

/* ---------- Visual helpers ---------- */

function kindAccent(kind: string): string {
  if (SECTIONS_KINDS.has(kind)) return 'amber'
  if (kind === 'picture') return 'green'
  if (kind === 'table') return 'blue'
  if (kind === 'list_item') return 'mute'
  if (kind === 'caption') return 'caption'
  if (kind === 'code' || kind === 'formula') return 'code'
  if (kind === 'footnote' || kind === 'page_footer') return 'mute'
  if (kind.startsWith('group')) return 'group'
  return 'gray'
}

function nodeLabel(n: DocNode): string {
  if (n.text) return n.text
  if (n.kind === 'picture') return 'picture'
  if (n.kind === 'table') return 'table'
  if (n.kind.startsWith('group')) return '(group children)'
  return n.ref
}

const INDENT_PX = 14
const INDENT_DEPTH_CAP = 8
function indentStyle(depth: number): { paddingLeft: string } {
  // Cap visual indent at depth 8 — deeper structures keep their semantic
  // depth in the data but stop pushing text off-screen.
  const capped = Math.min(depth, INDENT_DEPTH_CAP)
  return { paddingLeft: `${capped * INDENT_PX + 4}px` }
}
</script>

<template>
  <section class="pane doc">
    <header class="pane-head">
      <span class="label">STRUCTURE</span>
      <span v-if="docStore.hasDocument" class="badge mono">{{ totalCount }} nodes</span>
      <div class="actions">
        <button v-if="docStore.hasDocument" @click="docStore.clearDocument()">Replace</button>
        <button v-else class="primary" :disabled="docStore.converting" @click="pickFile">
          {{ docStore.converting ? 'Converting…' : 'Load file' }}
        </button>
      </div>
      <input
        ref="fileInput"
        type="file"
        accept="application/pdf,application/json,.pdf,.json"
        style="display: none"
        @change="onFile"
      />
    </header>

    <div v-if="docStore.hasDocument" class="toolbar">
      <div class="tabs" role="tablist">
        <button
          role="tab"
          :aria-selected="view === 'tree'"
          :class="{ active: view === 'tree' }"
          @click="view = 'tree'"
        >
          tree
        </button>
        <button
          role="tab"
          :aria-selected="view === 'by-type'"
          :class="{ active: view === 'by-type' }"
          @click="view = 'by-type'"
        >
          by type
        </button>
      </div>
      <input v-model="filter" type="text" class="filter-input" placeholder="Filter elements…" />
      <div class="tree-controls">
        <button class="ghost" title="Expand all" @click="expandAll">Expand</button>
        <button class="ghost" title="Collapse all" @click="collapseAll">Collapse</button>
      </div>
    </div>

    <div ref="scroller" class="body">
      <div v-if="!docStore.hasDocument" class="empty">
        <p v-if="docStore.converting">Converting PDF with Docling…</p>
        <template v-else>
          <p>
            Upload a <strong>PDF</strong> — Docling converts it server-side, then docling-agent
            walks the resulting <code>DoclingDocument</code> chunklessly to answer your questions.
          </p>
          <p class="alt">You can also load a pre-converted <code>DoclingDocument</code> JSON.</p>
        </template>
        <p v-if="docStore.convertError" class="parse-error">{{ docStore.convertError }}</p>
        <p v-if="parseError" class="parse-error">{{ parseError }}</p>
        <button class="primary" :disabled="docStore.converting" @click="pickFile">
          {{ docStore.converting ? 'Converting…' : 'Choose file…' }}
        </button>
      </div>

      <!-- tree view: pure body.children walk, per-node collapsible -->
      <ul v-else-if="view === 'tree'" class="tree">
        <li
          v-for="n in tree.visibleNodes.value"
          :key="n.ref"
          :data-ref="n.ref"
          class="node"
          :class="{
            active: focused.has(n.ref),
            collapsed: tree.collapsed.value.has(n.ref),
            parent: n.hasChildren,
            [`accent-${kindAccent(n.kind)}`]: true,
          }"
          :style="indentStyle(n.depth)"
          :title="`${n.ref} · depth ${n.depth} · ${n.kind}`"
          @click="onNodeClick(n)"
        >
          <button
            v-if="n.hasChildren"
            class="chev mono"
            :title="tree.collapsed.value.has(n.ref) ? 'Expand' : 'Collapse'"
            @click.stop="tree.toggleCollapse(n.ref)"
          >
            {{ tree.collapsed.value.has(n.ref) ? '▸' : '▾' }}
          </button>
          <span v-else class="chev-spacer" />
          <span class="bullet" aria-hidden="true" />
          <span class="kind-tag mono">{{ n.kind }}</span>
          <span class="text">{{ nodeLabel(n) }}</span>
          <span class="decos">
            <span
              v-for="(deco, i) in decorationsFor(n.ref)"
              :key="i"
              class="deco-badge mono"
              :class="[`color-${deco.color}`]"
              :title="deco.tooltip"
            >
              {{ deco.badge }}
            </span>
          </span>
          <span v-if="n.pageNo !== null" class="page-badge mono">p{{ n.pageNo }}</span>
        </li>
        <li v-if="tree.visibleNodes.value.length === 0" class="empty no-match">
          {{ filter ? 'No node matches the filter.' : 'Empty body tree.' }}
        </li>
      </ul>

      <!-- by-type view: inventory grouped by collection bucket -->
      <ul v-else class="tree">
        <li v-for="b in byTypeBuckets" :key="b.key" class="group">
          <button class="group-head" @click="toggleBucket(b)">
            <span class="chev mono" aria-hidden="true">
              {{ isBucketExpanded(b) ? '▾' : '▸' }}
            </span>
            <span class="group-dot" />
            <span class="group-tag mono">group</span>
            <span class="group-label">{{ b.label }}</span>
            <span class="group-count mono">{{ b.nodes.length }}</span>
          </button>
          <ul v-show="isBucketExpanded(b)" class="nodes">
            <li
              v-for="n in b.nodes"
              :key="`${b.key}:${n.ref}`"
              :data-ref="n.ref"
              class="node"
              :class="{
                active: focused.has(n.ref),
                [`accent-${kindAccent(n.kind)}`]: true,
              }"
              :style="indentStyle(1)"
              :title="`${n.ref} · ${n.kind}`"
              @click="onNodeClick(n)"
            >
              <span class="chev-spacer" />
              <span class="bullet" aria-hidden="true" />
              <span class="kind-tag mono">{{ n.kind }}</span>
              <span class="text">{{ nodeLabel(n) }}</span>
              <span class="decos">
                <span
                  v-for="(deco, i) in decorationsFor(n.ref)"
                  :key="i"
                  class="deco-badge mono"
                  :class="[`color-${deco.color}`]"
                  :title="deco.tooltip"
                >
                  {{ deco.badge }}
                </span>
              </span>
              <span v-if="n.pageNo !== null" class="page-badge mono">p{{ n.pageNo }}</span>
            </li>
          </ul>
        </li>
        <li v-if="byTypeBuckets.length === 0" class="empty no-match">
          No node matches the filter.
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.pane.doc {
  display: grid;
  grid-template-rows: auto auto 1fr;
  background: var(--surface);
}
.pane-head {
  display: grid;
  grid-template-columns: auto auto 1fr;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}
.label {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--ink-3);
  text-transform: uppercase;
}
.badge {
  font-size: 11px;
  color: var(--ink-3);
  background: var(--surface-2);
  border: 1px solid var(--border);
  padding: 1px 6px;
  border-radius: 3px;
}
.actions {
  justify-self: end;
  display: flex;
  gap: 4px;
}
.actions button {
  font-size: 11px;
  padding: 3px 8px;
}

.toolbar {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}
.tabs {
  display: flex;
  gap: 2px;
  background: var(--surface-2);
  border-radius: 6px;
  padding: 2px;
}
.tabs button {
  font-size: 11px;
  font-family: var(--mono);
  border: none;
  background: transparent;
  color: var(--ink-3);
  padding: 3px 10px;
  border-radius: 4px;
  cursor: pointer;
}
.tabs button:hover {
  color: var(--ink);
}
.tabs button.active {
  background: var(--surface);
  color: var(--ink);
  box-shadow: 0 1px 2px rgba(28, 27, 24, 0.06);
}
.filter-input {
  width: 100%;
  font-size: 12px;
  padding: 5px 10px;
}
.tree-controls {
  display: flex;
  gap: 2px;
}
.tree-controls .ghost {
  font-size: 11px;
  font-family: var(--mono);
  padding: 4px 8px;
  background: transparent;
  border-color: transparent;
  color: var(--ink-3);
}
.tree-controls .ghost:hover {
  background: var(--surface-2);
  color: var(--ink);
}

.body {
  overflow-y: auto;
  padding: 4px 6px 16px;
  min-height: 0;
}
.empty {
  color: var(--ink-3);
  font-size: 13px;
  text-align: center;
  padding: 24px;
}
.empty.no-match {
  padding: 16px;
}
.empty code {
  font-family: var(--mono);
  font-size: 12px;
  background: var(--surface-2);
  padding: 1px 4px;
  border-radius: 3px;
}
.empty strong {
  color: var(--ink-2);
}
.empty .alt {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ink-3);
}
.empty .primary {
  margin-top: 12px;
}
.parse-error {
  background: #fde7e2;
  border: 1px solid #f3b9ad;
  color: #87331f;
  padding: 8px 12px;
  font-family: var(--mono);
  font-size: 12px;
  border-radius: var(--radius);
  margin: 12px 0;
  text-align: left;
}

.tree {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.group {
  list-style: none;
  padding-bottom: 4px;
}
.group-head {
  display: grid;
  grid-template-columns: 14px 10px auto 1fr auto;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 5px 10px;
  cursor: pointer;
  font-size: 13px;
  color: var(--ink);
  background: transparent;
  text-align: left;
}
.group-head:hover {
  background: var(--surface-2);
}
.group-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--border-strong);
}
.group-tag {
  font-size: 10px;
  letter-spacing: 0.03em;
  color: var(--ink-3);
  background: var(--surface-2);
  border: 1px solid var(--border);
  padding: 0 5px;
  border-radius: 3px;
  white-space: nowrap;
}
.group-label {
  font-weight: 500;
}
.group-count {
  font-size: 10px;
  color: var(--ink-3);
  font-weight: 500;
}
.nodes {
  list-style: none;
  margin: 0;
  padding: 0;
}

.node {
  display: grid;
  /* chev · bullet · kind-tag · text · decos · page-badge */
  grid-template-columns: 14px 8px auto 1fr auto auto;
  align-items: center;
  gap: 6px;
  padding: 3px 8px 3px 0;
  border-radius: 3px;
  font-size: 12px;
  color: var(--ink-2);
  cursor: pointer;
  border-left: 2px solid transparent;
  list-style: none;
}
.node:hover {
  background: var(--surface-2);
}
.node.active {
  background: var(--citation);
  color: #5b4500;
  border-left-color: var(--citation-strong);
}

.chev {
  font-size: 10px;
  color: var(--ink-3);
  text-align: center;
  background: transparent;
  border: none;
  padding: 0;
  width: 14px;
  height: 14px;
  display: grid;
  place-items: center;
  border-radius: 2px;
  cursor: pointer;
}
.chev:hover {
  background: var(--surface);
  color: var(--ink);
}
.chev-spacer {
  width: 14px;
}

.bullet {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--ink-3);
  display: inline-block;
}
.node.accent-blue .bullet {
  background: #3d8ee0;
}
.node.accent-green .bullet {
  background: var(--accent);
}
.node.accent-amber .bullet {
  background: #d68433;
}
.node.accent-mute .bullet {
  background: var(--border-strong);
}
.node.accent-caption .bullet {
  background: #b59243;
}
.node.accent-code .bullet {
  background: #6a45d9;
}
.node.accent-group .bullet {
  background: var(--ink-3);
  border-radius: 1px;
}

.kind-tag {
  font-size: 10px;
  letter-spacing: 0.03em;
  color: var(--ink-3);
  background: var(--surface-2);
  border: 1px solid var(--border);
  padding: 0 5px;
  border-radius: 3px;
  white-space: nowrap;
  font-weight: 500;
}
.node.accent-blue .kind-tag {
  color: #1763c2;
  background: #ecf4fc;
  border-color: #c8defa;
}
.node.accent-green .kind-tag {
  color: var(--accent);
  background: var(--accent-soft);
  border-color: #b9e3cf;
}
.node.accent-amber .kind-tag {
  color: #a35d12;
  background: #fbe9d4;
  border-color: #ecc89f;
}
.node.accent-code .kind-tag {
  color: #5a32c0;
  background: #efe9fb;
  border-color: #d6c8f1;
  font-family: var(--mono);
}
.node.accent-caption .kind-tag {
  color: #7a5a14;
  background: #faf0d6;
  border-color: #e8d59a;
}
.node.accent-group .kind-tag {
  font-style: italic;
}

.text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: inherit;
  min-width: 0;
}
.node.accent-amber .text {
  font-weight: 600;
  color: var(--ink);
}
.node.accent-caption .text {
  font-style: italic;
  color: var(--ink-2);
}
.node.active .text {
  font-weight: 600;
}
.node.parent.collapsed .text {
  color: var(--ink-3);
}

.page-badge {
  font-size: 10px;
  color: var(--ink-3);
  background: transparent;
  border: 1px solid var(--border);
  padding: 0 5px;
  border-radius: 999px;
  white-space: nowrap;
}

/* Decoration badges — one small pill per feature signal attached to a
 * node. Hover surfaces the full value via the native title attribute,
 * which keeps the row footprint constant and avoids a popover dependency. */
.decos {
  display: flex;
  gap: 3px;
}
.deco-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.04em;
  border: 1px solid transparent;
  cursor: help;
}
.deco-badge.color-green {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: #b9e3cf;
}
.deco-badge.color-blue {
  background: #ecf4fc;
  color: #1763c2;
  border-color: #c8defa;
}
.deco-badge.color-amber {
  background: #fbe9d4;
  color: #a35d12;
  border-color: #ecc89f;
}
.deco-badge.color-purple {
  background: #efe9fb;
  color: #5a32c0;
  border-color: #d6c8f1;
}
.deco-badge.color-mute {
  background: var(--surface-2);
  color: var(--ink-3);
  border-color: var(--border);
}
.deco-badge.color-gray {
  background: var(--surface-2);
  color: var(--ink-2);
  border-color: var(--border);
}
</style>
