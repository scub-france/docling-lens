import { computed, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import type { DoclingDoc } from './parseDoc'
import { useDocTree } from './useDocTree'

/**
 * Build a tiny DoclingDocument that exercises the contract:
 * - body has 3 top-level children
 * - one child is a section_header with a real `children` array (nested)
 * - another child is a sibling paragraph at depth 0
 * - one item carries `prov[0].page_no`; another inherits via parent walk
 *
 * The shape mirrors what docling-core actually emits.
 */
function fixture(): DoclingDoc {
  return {
    body: {
      self_ref: '#/body',
      children: [{ $ref: '#/texts/0' }, { $ref: '#/texts/1' }, { $ref: '#/tables/0' }],
    },
    texts: [
      {
        self_ref: '#/texts/0',
        label: 'section_header',
        text: 'Introduction',
        prov: [{ page_no: 1 }],
        children: [{ $ref: '#/texts/2' }, { $ref: '#/texts/3' }],
      },
      {
        self_ref: '#/texts/1',
        label: 'paragraph',
        text: 'Sibling paragraph at root.',
        prov: [{ page_no: 1 }],
      },
      {
        self_ref: '#/texts/2',
        label: 'paragraph',
        text: 'First paragraph under Introduction.',
        prov: [{ page_no: 1 }],
      },
      {
        self_ref: '#/texts/3',
        label: 'paragraph',
        // No prov — should inherit page 1 from its parent.
        text: 'Inherits page from section_header.',
      },
    ],
    tables: [
      {
        self_ref: '#/tables/0',
        label: 'table',
        prov: [{ page_no: 2 }],
      },
    ],
  }
}

describe('useDocTree', () => {
  it('walks body.children preserving depth + parent links + page inheritance', () => {
    const doc = computed(() => fixture())
    const filter = ref('')
    const tree = useDocTree(doc, filter)

    const nodes = tree.allNodes.value
    expect(nodes.map((n) => n.ref)).toEqual([
      '#/texts/0',
      '#/texts/2',
      '#/texts/3',
      '#/texts/1',
      '#/tables/0',
    ])
    // Depths: 0 (section), 1 + 1 (children), 0 (sibling), 0 (table)
    expect(nodes.map((n) => n.depth)).toEqual([0, 1, 1, 0, 0])
    // Parent refs reflect docling's own children arrays.
    const byRef = new Map(nodes.map((n) => [n.ref, n]))
    expect(byRef.get('#/texts/2')?.parentRef).toBe('#/texts/0')
    expect(byRef.get('#/texts/3')?.parentRef).toBe('#/texts/0')
    expect(byRef.get('#/texts/1')?.parentRef).toBeNull()
    // Page inheritance: texts/3 has no prov but lives under page-1 section.
    expect(byRef.get('#/texts/3')?.pageNo).toBe(1)
    expect(byRef.get('#/tables/0')?.pageNo).toBe(2)
    // hasChildren is honest.
    expect(byRef.get('#/texts/0')?.hasChildren).toBe(true)
    expect(byRef.get('#/texts/1')?.hasChildren).toBe(false)
  })

  it('collapse hides the entire subtree of a parent', () => {
    const doc = computed(() => fixture())
    const filter = ref('')
    const tree = useDocTree(doc, filter)

    expect(tree.visibleNodes.value.map((n) => n.ref)).toHaveLength(5)
    tree.toggleCollapse('#/texts/0')
    // Section + its 2 children disappear; root sibling + table remain.
    expect(tree.visibleNodes.value.map((n) => n.ref)).toEqual([
      '#/texts/0',
      '#/texts/1',
      '#/tables/0',
    ])
    tree.toggleCollapse('#/texts/0')
    expect(tree.visibleNodes.value.map((n) => n.ref)).toHaveLength(5)
  })

  it('collapseAll then uncollapseAncestors opens just the path to a target', () => {
    const doc = computed(() => fixture())
    const filter = ref('')
    const tree = useDocTree(doc, filter)

    tree.collapseAll()
    // Only collapsible (parent) nodes are collapsed; siblings stay visible.
    expect(tree.collapsed.value.has('#/texts/0')).toBe(true)
    expect(tree.visibleNodes.value.find((n) => n.ref === '#/texts/2')).toBeUndefined()

    tree.uncollapseAncestors(['#/texts/3'])
    // Ancestor section opened → its children come back.
    expect(tree.collapsed.value.has('#/texts/0')).toBe(false)
    expect(tree.visibleNodes.value.find((n) => n.ref === '#/texts/3')).toBeDefined()
  })

  it('filter bypasses collapse state', () => {
    const doc = computed(() => fixture())
    const filter = ref('')
    const tree = useDocTree(doc, filter)

    tree.collapseAll()
    expect(tree.visibleNodes.value.find((n) => n.ref === '#/texts/2')).toBeUndefined()
    filter.value = 'first paragraph'
    // Filter mode ignores collapse — match shows up.
    expect(tree.visibleNodes.value.map((n) => n.ref)).toEqual(['#/texts/2'])
  })

  it('returns an empty list for a document with no body', () => {
    const doc = computed<DoclingDoc | null>(() => ({ body: undefined }))
    const filter = ref('')
    const tree = useDocTree(doc, filter)
    expect(tree.allNodes.value).toEqual([])
    expect(tree.visibleNodes.value).toEqual([])
  })

  it('guards against cycles in the children graph', () => {
    const cyclic: DoclingDoc = {
      body: { children: [{ $ref: '#/texts/0' }] },
      texts: [
        // self-ref cycle: texts/0 → texts/1 → texts/0
        { self_ref: '#/texts/0', children: [{ $ref: '#/texts/1' }] },
        { self_ref: '#/texts/1', children: [{ $ref: '#/texts/0' }] },
      ],
    }
    const doc = computed(() => cyclic)
    const filter = ref('')
    const tree = useDocTree(doc, filter)
    expect(tree.allNodes.value.map((n) => n.ref)).toEqual(['#/texts/0', '#/texts/1'])
  })
})
