/**
 * `useDocTree` — body-tree walk + collapse / focus state.
 *
 * Pulled out of `DocumentPane.vue` so the parsing logic, the parent map,
 * and the visible-subset computation can be reasoned about (and tested)
 * independently of the Vue template that consumes them. The composable
 * is intentionally view-mode agnostic — the by-type inventory in
 * `DocumentPane.vue` reuses the same `allNodes` source.
 */

import { computed, ref, type ComputedRef, type Ref } from 'vue'

import { extractRef, getByRef, kindFromRef, type DocItem, type DoclingDoc } from './parseDoc'

/** Hard ceiling so a pathological document can't lock the pane up.
 *  Real research PDFs we've seen sit around 1-2k nodes; 5k is comfortable
 *  headroom. Surface a UI signal if we ever truncate. */
export const WALK_NODE_CAP = 5000

export interface DocNode {
  ref: string
  kind: string
  text: string
  /** Depth as docling produced it — preserves the upstream hierarchy. */
  depth: number
  pageNo: number | null
  hasChildren: boolean
  /** Parent ref in the body tree; `null` for direct body children. */
  parentRef: string | null
}

const TEXT_PREVIEW_CHARS = 240

function walkBody(doc: DoclingDoc): DocNode[] {
  const body = doc.body
  if (!body) return []

  const out: DocNode[] = []
  const visited = new Set<string>()

  const visit = (
    refStr: string,
    depth: number,
    parentPage: number | null,
    parentRef: string | null,
  ): void => {
    if (out.length >= WALK_NODE_CAP) return
    if (visited.has(refStr)) return
    visited.add(refStr)
    const item = getByRef(doc, refStr)
    if (!item) return

    const ownPage = item.prov?.[0]?.page_no ?? null
    const pageNo = typeof ownPage === 'number' ? ownPage : parentPage
    const childRefs = childRefsOf(item)

    out.push({
      ref: refStr,
      kind: kindFromRef(refStr, item),
      text: (item.text || '').slice(0, TEXT_PREVIEW_CHARS),
      depth,
      pageNo,
      hasChildren: childRefs.length > 0,
      parentRef,
    })

    for (const cref of childRefs) visit(cref, depth + 1, pageNo, refStr)
  }

  const rootChildren = Array.isArray(body.children) ? body.children : []
  for (const c of rootChildren) {
    const cref = extractRef(c)
    if (cref) visit(cref, 0, null, null)
  }
  return out
}

function childRefsOf(item: DocItem): string[] {
  const children = Array.isArray(item.children) ? item.children : []
  const out: string[] = []
  for (const c of children) {
    const r = extractRef(c)
    if (r) out.push(r)
  }
  return out
}

export interface UseDocTreeReturn {
  /** Full pre-order walk of `body.children`. */
  allNodes: ComputedRef<DocNode[]>
  /** ref → parentRef map; useful to walk ancestors on focus. */
  parentMap: ComputedRef<Map<string, string | null>>
  /** Refs whose subtree is currently hidden. */
  collapsed: Ref<Set<string>>
  /** Visible subset: filtered (when `query` non-empty) or collapse-aware. */
  visibleNodes: ComputedRef<DocNode[]>
  toggleCollapse: (ref: string) => void
  /** Empty the collapsed set. */
  expandAll: () => void
  /** Collapse every node that has children — user drills back in. */
  collapseAll: () => void
  /** Walk ancestors of each `ref` and remove them from `collapsed`. */
  uncollapseAncestors: (refs: Iterable<string>) => void
}

export function useDocTree(
  doc: ComputedRef<DoclingDoc | null>,
  query: Ref<string>,
): UseDocTreeReturn {
  const allNodes = computed<DocNode[]>(() => (doc.value ? walkBody(doc.value) : []))

  const parentMap = computed<Map<string, string | null>>(() => {
    const m = new Map<string, string | null>()
    for (const n of allNodes.value) m.set(n.ref, n.parentRef)
    return m
  })

  const collapsed = ref<Set<string>>(new Set())

  /**
   * Skip subtrees rooted at a collapsed ref using a single pass over the
   * pre-order list: any node strictly deeper than the current `skipBelow`
   * threshold is hidden until we surface back to that depth or above.
   * O(n) — no per-item ancestor walk.
   */
  const visibleNodes = computed<DocNode[]>(() => {
    const q = query.value.trim().toLowerCase()
    if (q) {
      return allNodes.value.filter(
        (n) => n.text.toLowerCase().includes(q) || n.ref.toLowerCase().includes(q),
      )
    }
    const out: DocNode[] = []
    let skipBelow = Infinity
    for (const n of allNodes.value) {
      if (n.depth > skipBelow) continue
      skipBelow = Infinity
      out.push(n)
      if (n.hasChildren && collapsed.value.has(n.ref)) skipBelow = n.depth
    }
    return out
  })

  function toggleCollapse(refStr: string): void {
    const next = new Set(collapsed.value)
    if (next.has(refStr)) next.delete(refStr)
    else next.add(refStr)
    collapsed.value = next
  }

  function expandAll(): void {
    collapsed.value = new Set()
  }

  function collapseAll(): void {
    const s = new Set<string>()
    for (const n of allNodes.value) if (n.hasChildren) s.add(n.ref)
    collapsed.value = s
  }

  function uncollapseAncestors(refs: Iterable<string>): void {
    const next = new Set(collapsed.value)
    for (const r of refs) {
      let cur = parentMap.value.get(r) ?? null
      while (cur) {
        next.delete(cur)
        cur = parentMap.value.get(cur) ?? null
      }
    }
    collapsed.value = next
  }

  return {
    allNodes,
    parentMap,
    collapsed,
    visibleNodes,
    toggleCollapse,
    expandAll,
    collapseAll,
    uncollapseAncestors,
  }
}
