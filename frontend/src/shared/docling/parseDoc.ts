/**
 * DoclingDocument — wire types + navigation helpers.
 *
 * Single source of truth for the shape of items we read out of the
 * serialized JSON. Both the structure tree (`DocumentPane`) and the
 * PDF bbox overlay (`PdfViewer`) consume the same primitives so the
 * `JSON.parse` cost is paid once (in the store) and the ref-resolution
 * logic doesn't drift between the two views.
 *
 * Only the fields docling-lens actually touches are typed — anything
 * else stays `unknown` to avoid pretending we own the whole upstream
 * schema. If a new field becomes relevant, add it here.
 */

export interface DocBbox {
  l: number
  t: number
  r: number
  b: number
  coord_origin?: string
}

export interface DocProv {
  page_no?: number
  bbox?: DocBbox
}

export interface DocItem {
  self_ref?: string
  label?: string
  text?: string
  children?: unknown[]
  prov?: DocProv[]
}

export interface DoclingDoc {
  body?: DocItem
  texts?: DocItem[]
  tables?: DocItem[]
  pictures?: DocItem[]
  groups?: DocItem[]
  [k: string]: unknown
}

interface RefLike {
  $ref?: string
  cref?: string
}

/** Pull the `#/...` ref out of a `{$ref}` / `{cref}` payload, if any. */
export function extractRef(r: unknown): string | null {
  if (!r || typeof r !== 'object') return null
  const obj = r as RefLike
  if (typeof obj.$ref === 'string') return obj.$ref
  if (typeof obj.cref === 'string') return obj.cref
  return null
}

/** Resolve a `#/<collection>/<idx>` (or `#/body`) ref against the document. */
export function getByRef(doc: DoclingDoc, ref: string): DocItem | null {
  if (ref === '#/body') return doc.body ?? null
  const m = ref.match(/^#\/([^/]+)\/(\d+)$/)
  if (!m) return null
  const arr = (doc as Record<string, unknown>)[m[1]]
  if (!Array.isArray(arr)) return null
  return (arr[Number(m[2])] as DocItem | undefined) ?? null
}

/**
 * Synthesize a kind name for an item.
 *
 * For `texts/*`, the upstream `label` carries the real semantic kind
 * (`section_header`, `paragraph`, `caption`, `title`, `list_item`, …).
 * For `tables` / `pictures` we use the collection name as the kind.
 * For `groups`, we expose the group label as `group/<label>` so the UI
 * can show structural groupings (lists, inlines, chapters) distinctly
 * from raw groups.
 */
export function kindFromRef(ref: string, item: DocItem): string {
  if (ref.startsWith('#/tables/')) return 'table'
  if (ref.startsWith('#/pictures/')) return 'picture'
  if (ref.startsWith('#/groups/')) return item.label ? `group/${item.label}` : 'group'
  return item.label || 'text'
}

/** Safe `JSON.parse` returning null for non-object / invalid input. */
export function parseDoc(json: string | null): DoclingDoc | null {
  if (!json) return null
  try {
    const obj = JSON.parse(json) as unknown
    if (obj && typeof obj === 'object') return obj as DoclingDoc
  } catch {
    /* fall through */
  }
  return null
}
