<script setup lang="ts">
/**
 * Enrich debugger page — symmetric with `RagDebuggerPage`. Shares the
 * `WorkspaceShell` + `DocumentPane` + `TopBar` from `shared/`; provides
 * its own composer, timeline, status bar, and computes the per-node
 * decorations the shared `DocumentPane` renders next to each tree node.
 */
import { computed } from 'vue'

import EnrichComposer from './EnrichComposer.vue'
import EnrichStatusBar from './EnrichStatusBar.vue'
import EnrichTimelinePane from './EnrichTimelinePane.vue'
import { useEnrichStore } from '../store'
import type { EnrichOperation, NodeEnrichment } from '../types'
import DocumentPane from '@/shared/workspace/DocumentPane.vue'
import type { DecorationsMap, NodeDecoration } from '@/shared/workspace/decorations'
import WorkspaceShell from '@/shared/workspace/WorkspaceShell.vue'

const store = useEnrichStore()

// Single-letter badges + accent colors — matches the timeline's per-op
// palette so the eye links a green "S" in the tree to the green
// "SUMMARIZE" block in the center pane.
const OP_BADGE: Record<EnrichOperation, NodeDecoration> = {
  summarize: { badge: 'S', color: 'green' },
  keywords: { badge: 'K', color: 'blue' },
  entities: { badge: 'E', color: 'purple' },
}

interface EntityShape {
  entity_type?: unknown
  mention?: unknown
}
function isEntity(x: unknown): x is EntityShape {
  return typeof x === 'object' && x !== null && ('entity_type' in x || 'mention' in x)
}

/**
 * Tooltip surface — what shows on hover of a badge in the tree. Uses the
 * same per-op rendering rules as the timeline center pane so the badge
 * and the row stay consistent (`mention (TYPE)` for entities, etc.).
 */
function renderTooltip(e: NodeEnrichment): string {
  const v = e.value
  if (v == null) return e.operation
  if (e.operation === 'entities' && Array.isArray(v)) {
    const parts = v.map((x) => {
      if (isEntity(x)) {
        const mention = typeof x.mention === 'string' ? x.mention : ''
        const type = typeof x.entity_type === 'string' ? x.entity_type : ''
        if (mention && type) return `${mention} (${type})`
        return mention || type || JSON.stringify(x)
      }
      return typeof x === 'string' ? x : JSON.stringify(x)
    })
    return `${e.operation}: ${parts.join(', ')}`
  }
  if (typeof v === 'string') return `${e.operation}: ${v}`
  if (Array.isArray(v)) {
    const parts = v.map((x) => (typeof x === 'string' ? x : JSON.stringify(x)))
    return `${e.operation}: ${parts.join(', ')}`
  }
  if (typeof v === 'object') return `${e.operation}: ${JSON.stringify(v)}`
  return `${e.operation}: ${String(v)}`
}

/**
 * Map every (selfRef → [decorations]) from the active run. Built as a
 * fresh Map per change so the shared pane's prop comparison stays cheap
 * (Vue compares refs, and we always hand it a new identity when the
 * underlying enrichments change).
 */
const decorations = computed<DecorationsMap>(() => {
  const map = new Map<string, NodeDecoration[]>()
  for (const e of store.activeEnrichments) {
    const template = OP_BADGE[e.operation]
    const list = map.get(e.selfRef) ?? []
    list.push({ ...template, tooltip: renderTooltip(e) })
    map.set(e.selfRef, list)
  }
  return map
})
</script>

<template>
  <WorkspaceShell>
    <template #left-pane>
      <EnrichComposer />
    </template>
    <template #center-pane>
      <EnrichTimelinePane />
    </template>
    <template #right-pane>
      <DocumentPane :decorations="decorations" />
    </template>
    <template #status-bar>
      <EnrichStatusBar />
    </template>
  </WorkspaceShell>
</template>
