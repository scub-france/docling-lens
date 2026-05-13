<script setup lang="ts">
/**
 * PDF viewer with DoclingDocument bbox overlay.
 *
 * Each page is rendered to a canvas via PDF.js, and a sibling `<div class=
 * "overlay">` carries one absolutely-positioned box per text/table/picture
 * item that lives on that page. Boxes whose `self_ref` is in the active
 * step's citations get the highlighted styling and are scrolled into view.
 *
 * Coordinate handling: docling-core emits PDF bboxes with `coord_origin`
 * = "BOTTOMLEFT" by default — the y-axis grows upward and `t` is the
 * top edge (so `t > b`). We convert to CSS top-left coordinates per
 * page. TOPLEFT bboxes are passed through as-is.
 *
 * The pdf.js worker is bundled via Vite's `?url` import so it ships with
 * the app and doesn't rely on a CDN.
 */
import * as pdfjsLib from 'pdfjs-dist'
import PdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import type { DoclingDoc, DocItem } from '../docling/parseDoc'

pdfjsLib.GlobalWorkerOptions.workerSrc = PdfWorkerUrl as string

const props = defineProps<{
  pdfBlob: Blob | null
  /**
   * Pre-parsed DoclingDocument from the store. We deliberately don't
   * accept the raw JSON string — `store.parsedDocument` is the single
   * source of truth, so we avoid re-parsing on every PDF render.
   */
  parsedDocument: DoclingDoc | null
  activeCitations: string[]
  /**
   * Monotonic counter — bumps even when the user re-clicks the *same*
   * step. Watching `activeCitations` alone wouldn't refire the scroll in
   * that case (same array → no change). We trigger off this instead.
   */
  focusTick: number
}>()

interface Overlay {
  ref: string
  label: string
  // CSS-space coordinates relative to the page (already scaled).
  left: number
  top: number
  width: number
  height: number
}

const container = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const pages = ref<
  Array<{
    pageNo: number
    width: number
    height: number
    overlays: Overlay[]
  }>
>([])

/**
 * Pre-order walk of `texts` / `tables` / `pictures` collections, yielding
 * a normalized `self_ref` and a default label per collection. The bbox
 * overlay only cares about items that carry `prov[0].bbox` — the body
 * tree is irrelevant here (we draw boxes on every leaf with coordinates,
 * not just those reachable from `body.children`).
 */
function* iterBboxItems(
  doc: DoclingDoc,
): Generator<{ collection: string; index: number; item: DocItem & { self_ref: string } }> {
  const collections: Array<[keyof DoclingDoc, string]> = [
    ['texts', 'text'],
    ['tables', 'table'],
    ['pictures', 'picture'],
  ]
  for (const [key, defaultLabel] of collections) {
    const arr = doc[key]
    if (!Array.isArray(arr)) continue
    for (let i = 0; i < arr.length; i++) {
      const it = arr[i] as DocItem | undefined
      if (!it) continue
      yield {
        collection: String(key),
        index: i,
        item: {
          ...it,
          self_ref: it.self_ref || `#/${String(key)}/${i}`,
          label: it.label || defaultLabel,
        },
      }
    }
  }
}

let currentRenderId = 0
let currentDoc: pdfjsLib.PDFDocumentProxy | null = null

async function render(): Promise<void> {
  // Bump the render id so an in-flight render aborts when a new one starts.
  const myId = ++currentRenderId
  pages.value = []
  error.value = null
  if (!props.pdfBlob) return
  loading.value = true
  try {
    const buf = await props.pdfBlob.arrayBuffer()
    if (myId !== currentRenderId) return
    const doc = await pdfjsLib.getDocument({ data: buf }).promise
    if (myId !== currentRenderId) {
      doc.destroy()
      return
    }
    if (currentDoc) currentDoc.destroy()
    currentDoc = doc

    const docJson = props.parsedDocument
    const itemsByPage = new Map<number, Array<DocItem & { self_ref: string }>>()
    if (docJson) {
      for (const { item } of iterBboxItems(docJson)) {
        const prov = item.prov?.[0]
        const pageNo = prov?.page_no
        if (typeof pageNo !== 'number') continue
        const list = itemsByPage.get(pageNo) ?? []
        list.push(item)
        itemsByPage.set(pageNo, list)
      }
    }

    const SCALE = 1.5 // visual density — tuned for legibility on 14" displays.
    const next: typeof pages.value = []

    for (let pageNo = 1; pageNo <= doc.numPages; pageNo++) {
      if (myId !== currentRenderId) return
      const page = await doc.getPage(pageNo)
      const viewport = page.getViewport({ scale: SCALE })
      const canvas = document.createElement('canvas')
      canvas.width = viewport.width
      canvas.height = viewport.height
      canvas.style.width = `${viewport.width}px`
      canvas.style.height = `${viewport.height}px`
      const ctx = canvas.getContext('2d')
      if (!ctx) continue
      await page.render({ canvasContext: ctx, viewport }).promise
      if (myId !== currentRenderId) return

      const overlays: Overlay[] = []
      const pageH = page.view[3] - page.view[1] // PDF user-unit height
      const docItems = itemsByPage.get(pageNo) ?? []
      for (const it of docItems) {
        const bb = it.prov?.[0]?.bbox
        if (!bb) continue
        const origin = (bb.coord_origin || 'BOTTOMLEFT').toUpperCase()
        let topUu: number
        let heightUu: number
        if (origin === 'TOPLEFT') {
          topUu = bb.t
          heightUu = Math.max(bb.b - bb.t, 0)
        } else {
          // BOTTOMLEFT: convert y-up to y-down. bbox.t is the upper edge
          // measured from the page bottom, so the CSS top = pageH - t.
          topUu = pageH - bb.t
          heightUu = Math.max(bb.t - bb.b, 0)
        }
        const leftUu = bb.l
        const widthUu = Math.max(bb.r - bb.l, 0)
        overlays.push({
          ref: it.self_ref,
          label: it.label || 'text',
          left: leftUu * SCALE,
          top: topUu * SCALE,
          width: widthUu * SCALE,
          height: heightUu * SCALE,
        })
      }

      next.push({
        pageNo,
        width: viewport.width,
        height: viewport.height,
        overlays,
      })
      // Append progressively so the user sees pages appear as they're ready.
      pages.value = [...next]
      // Mount the just-rendered canvas into its slot once the DOM tick lands.
      await nextTick()
      const slot = container.value?.querySelector<HTMLElement>(
        `[data-page="${pageNo}"] .canvas-host`,
      )
      if (slot) {
        slot.replaceChildren(canvas)
      }
    }
  } catch (e) {
    if (myId === currentRenderId) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  } finally {
    if (myId === currentRenderId) loading.value = false
  }
}

const activeSet = computed(() => new Set(props.activeCitations))

watch(
  () => [props.pdfBlob, props.parsedDocument],
  () => {
    void render()
  },
  { immediate: true },
)

watch(
  () => props.focusTick,
  async () => {
    await nextTick()
    if (!container.value || props.activeCitations.length === 0) return
    const first = props.activeCitations[0]
    const el = container.value.querySelector<HTMLElement>(`[data-ref="${CSS.escape(first)}"]`)
    if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' })
  },
)

onBeforeUnmount(() => {
  currentRenderId++
  if (currentDoc) {
    currentDoc.destroy()
    currentDoc = null
  }
})
</script>

<template>
  <div ref="container" class="pdf-viewer">
    <p v-if="!pdfBlob" class="empty">
      No PDF in this session. Upload a PDF in the document pane to see it here.
    </p>
    <p v-else-if="error" class="error">PDF render failed: {{ error }}</p>
    <p v-else-if="loading && pages.length === 0" class="empty">Rendering pages…</p>

    <div v-for="p in pages" :key="p.pageNo" class="page" :data-page="p.pageNo">
      <div class="page-label mono">page {{ p.pageNo }}</div>
      <div class="page-frame" :style="{ width: p.width + 'px', height: p.height + 'px' }">
        <div class="canvas-host" />
        <div class="overlay">
          <div
            v-for="o in p.overlays"
            :key="o.ref"
            :data-ref="o.ref"
            class="box"
            :class="{ active: activeSet.has(o.ref), [`label-${o.label}`]: true }"
            :style="{
              left: o.left + 'px',
              top: o.top + 'px',
              width: o.width + 'px',
              height: o.height + 'px',
            }"
            :title="o.ref"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pdf-viewer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 8px 12px 24px;
}
.empty,
.error {
  color: var(--ink-3);
  font-size: 13px;
  padding: 24px;
  text-align: center;
}
.error {
  color: #c0392b;
}
.page {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
}
.page-label {
  font-size: 10px;
  color: var(--ink-3);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.page-frame {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.canvas-host {
  position: absolute;
  inset: 0;
}
.overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.box {
  position: absolute;
  border: 1px solid rgba(124, 122, 114, 0.25);
  border-radius: 2px;
  background: transparent;
  transition:
    background 0.12s ease,
    border-color 0.12s ease,
    box-shadow 0.12s ease;
  pointer-events: auto;
}
.box:hover {
  border-color: var(--accent);
  background: rgba(30, 168, 113, 0.08);
}
.box.label-table {
  border-color: rgba(23, 99, 194, 0.45);
}
.box.label-picture {
  border-color: rgba(214, 132, 51, 0.55);
}
.box.active {
  border-color: var(--citation-strong);
  background: rgba(246, 201, 69, 0.28);
  box-shadow: 0 0 0 2px var(--citation-strong);
}
</style>
