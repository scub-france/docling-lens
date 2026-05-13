<script setup lang="ts">
/**
 * Gantt-style timeline view of a `ReasoningTrace`.
 *
 * Layout per row: kind badge · KIND label · title · bar zone · duration · tokens.
 * The bar zone shares a single time axis at the top of the pane so every
 * bar reads left-to-right against the same scale.
 *
 * docling-agent v0.1.0 doesn't ship per-step start/duration, so we synthesize:
 * - if any step has a non-zero `durationMs`, we cumsum durations to derive
 *   each step's start offset (the layout reflects real ordering),
 * - otherwise we evenly distribute steps across `totalDurationMs` so the
 *   pane still feels alive and ordering is preserved.
 *
 * Per-kind colors live in the scoped `<style>` below; they're the source
 * of truth for the visual identity of each step kind across the app.
 */
import { computed } from 'vue'

import type { ReasoningStep, ReasoningStepKind, ReasoningTrace } from '../types'

const props = defineProps<{
  trace: ReasoningTrace
  activeStepId: string | null
}>()

defineEmits<{
  (e: 'select', id: string): void
}>()

interface LaidOutStep {
  step: ReasoningStep
  leftPct: number
  widthPct: number
  startMs: number
  endMs: number
}

/**
 * `true` when none of the steps carry a real per-step duration. docling-
 * agent v0.1.0 doesn't expose iteration timing, so we fall back to even
 * spread. We surface that to the UI so per-row "3.04s" labels can be
 * hidden — showing identical durations on every row is misleading.
 */
const isSynthetic = computed(
  () => props.trace.steps.reduce((acc, s) => acc + (s.durationMs || 0), 0) === 0,
)

const layout = computed<LaidOutStep[]>(() => {
  const steps = props.trace.steps
  if (steps.length === 0) return []
  const sumDur = steps.reduce((acc, s) => acc + (s.durationMs || 0), 0)
  const total = Math.max(props.trace.totalDurationMs, sumDur, 1)

  if (sumDur > 0) {
    let cursor = 0
    return steps.map((step) => {
      const dur = step.durationMs || 0
      const startMs = cursor
      const endMs = cursor + dur
      cursor = endMs
      return {
        step,
        startMs,
        endMs,
        leftPct: (startMs / total) * 100,
        // Keep bars at least 1% wide so 0-duration synthetic steps still
        // render as a tick instead of vanishing.
        widthPct: Math.max((dur / total) * 100, 1),
      }
    })
  }

  // Even spread fallback — slot per step, bar fills 80% of its slot.
  const slot = 100 / steps.length
  const barFill = 0.8
  return steps.map((step, i) => {
    const startMs = (i / steps.length) * total
    const endMs = ((i + 1) / steps.length) * total
    return {
      step,
      startMs,
      endMs,
      leftPct: i * slot,
      widthPct: slot * barFill,
    }
  })
})

interface AxisTick {
  pct: number
  label: string
}

const axisTicks = computed<AxisTick[]>(() => {
  const total = Math.max(props.trace.totalDurationMs, 1)
  // 5 evenly-spaced ticks across the axis. Labels in ms when the run is
  // short (< 5s), seconds otherwise — matches what a debugger user expects.
  const count = 5
  const useSeconds = total >= 5000
  return Array.from({ length: count }, (_, i) => {
    const ms = (i / (count - 1)) * total
    const label = useSeconds ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`
    return { pct: (i / (count - 1)) * 100, label }
  })
})

const KIND_LABELS: Record<ReasoningStepKind, string> = {
  plan: 'PLAN',
  retrieve: 'RETRIEVE',
  rerank: 'RERANK',
  read: 'READ',
  verify: 'VERIFY',
  answer: 'ANSWER',
  map: 'MAP',
}

function fmtDuration(ms: number): string {
  if (ms <= 0) return ''
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`
  return `${Math.round(ms)}ms`
}

function fmtTokens(n: number): string {
  if (n <= 0) return '0t'
  return `${n}t`
}
</script>

<template>
  <div class="gantt">
    <div class="axis">
      <div class="axis-spacer" />
      <div class="axis-track">
        <span
          v-for="(tick, i) in axisTicks"
          :key="i"
          class="tick"
          :style="{ left: tick.pct + '%' }"
        >
          {{ tick.label }}
        </span>
      </div>
      <div class="axis-meta" />
    </div>

    <button
      v-for="row in layout"
      :key="row.step.id"
      type="button"
      class="row"
      :class="{
        active: row.step.id === activeStepId,
        synthetic: isSynthetic,
        answered: row.step.payload.can_answer === true,
        explored: row.step.payload.can_answer === false,
        [`kind-${row.step.kind}`]: true,
      }"
      @click="$emit('select', row.step.id)"
    >
      <span class="label mono">{{ KIND_LABELS[row.step.kind] }}</span>
      <span class="title">
        <span class="title-text">{{ row.step.title }}</span>
        <!--
          docling-agent's `can_answer` is the agent's per-iteration self-assessment.
          We surface it as a small chip so the user sees at a glance which sections
          the agent considered productive vs. exploratory.
        -->
        <span
          v-if="row.step.payload.can_answer === true"
          class="chip chip-answered mono"
          title="Agent declared this section sufficient"
        >
          answered
        </span>
        <span
          v-else-if="row.step.payload.can_answer === false"
          class="chip chip-explored mono"
          title="Agent read this section but kept looking"
        >
          explored
        </span>
        <span v-if="row.step.citations[0]" class="chip-ref mono">{{ row.step.citations[0] }}</span>
      </span>
      <span class="track">
        <span
          class="bar"
          :style="{ left: row.leftPct + '%', width: row.widthPct + '%' }"
          :title="
            isSynthetic
              ? `${row.step.title} · per-step timing not available`
              : `${row.step.title} · ${fmtDuration(row.endMs - row.startMs)}`
          "
        />
      </span>
      <span class="meta mono">
        <!--
          Synthetic mode: docling-agent doesn't ship per-step timing, so the
          bars are evenly distributed across `totalDurationMs`. Showing the
          same fake "3.04s" on every row was misleading — hide it.
        -->
        <span v-if="!isSynthetic" class="dur">{{
          fmtDuration(row.endMs - row.startMs) || '—'
        }}</span>
        <span class="tok">{{ fmtTokens(row.step.tokenCount) }}</span>
      </span>
    </button>

    <p v-if="isSynthetic" class="footnote mono">
      Bars are evenly distributed — docling-agent v0.1.0 doesn't expose per-step timing.
    </p>
  </div>
</template>

<style scoped>
.gantt {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
/* 4 columns shared with `.row` so axis ticks align with the bar zone:
 * KIND label · title · bar zone · duration/tokens. */
.axis,
.row {
  display: grid;
  grid-template-columns: 80px minmax(180px, 1.4fr) minmax(220px, 3fr) 110px;
  align-items: center;
  gap: 12px;
}
.axis {
  padding: 0 8px 6px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 4px;
}
.axis-spacer {
  grid-column: 1 / span 2;
}
.axis-track {
  position: relative;
  height: 16px;
}
.tick {
  position: absolute;
  top: 0;
  transform: translateX(-50%);
  font-size: 10px;
  color: var(--ink-3);
  white-space: nowrap;
}
.tick::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -6px;
  width: 1px;
  height: 5px;
  background: var(--border-strong);
}
.axis-meta {
  grid-column: 4;
}

.row {
  width: 100%;
  background: transparent;
  border: 1px solid transparent;
  border-left: 3px solid transparent;
  border-radius: var(--radius);
  padding: 6px 10px;
  cursor: pointer;
  text-align: left;
  transition:
    background 0.12s ease,
    border-color 0.12s ease;
}
.row:hover {
  background: var(--surface-2);
}

/* "answered" steps are the agent's productive moves — light green wash
 * across the whole row, accent border on the left. "explored" steps are
 * dimmed slightly so the productive ones really pop when scanning. */
.row.answered {
  background: #ecf7f0;
  border-color: rgba(30, 168, 113, 0.18);
  border-left-color: var(--accent);
}
.row.answered:hover {
  background: #e0f1e8;
}
.row.explored {
  background: #fbfaf6;
  border-color: var(--border);
  border-left-color: var(--border-strong);
  opacity: 0.92;
}
.row.explored:hover {
  background: var(--surface-2);
  opacity: 1;
}

.row.active {
  background: var(--citation);
  border-color: var(--citation-strong);
  border-left-color: var(--citation-strong);
}
.row.active.answered,
.row.active.explored {
  background: var(--citation);
  border-color: var(--citation-strong);
  border-left-color: var(--citation-strong);
  opacity: 1;
}

.label {
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--ink-3);
}
.row.answered .label {
  color: var(--accent);
}
.row.explored .label {
  color: var(--ink-3);
}
.title {
  font-size: 12px;
  color: var(--ink);
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.title-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  flex: 0 1 auto;
}
.chip {
  font-size: 10px;
  letter-spacing: 0.04em;
  padding: 1px 6px;
  border-radius: 999px;
  white-space: nowrap;
  flex-shrink: 0;
}
.chip-answered {
  background: var(--accent-soft);
  color: var(--accent);
}
.chip-explored {
  background: var(--surface-2);
  color: var(--ink-3);
  border: 1px solid var(--border);
}
.chip-ref {
  font-size: 10px;
  color: var(--ink-3);
  flex-shrink: 0;
}
/* `explored` rows are visually dimmed via the row background/opacity above;
 * we also tone the bar down a hair so productive steps stand out. */
.row.explored .bar {
  opacity: 0.65;
}

.track {
  position: relative;
  height: 14px;
  background: linear-gradient(to right, transparent calc(100% - 1px), var(--border) 100%);
  border-radius: 3px;
}
.bar {
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 3px;
  background: var(--ink-3);
  min-width: 4px;
}
.row.kind-plan .bar {
  background: #8b66ea;
}
.row.kind-retrieve .bar {
  background: #3d8ee0;
}
.row.kind-rerank .bar {
  background: #d68433;
}
.row.kind-read .bar {
  background: var(--accent);
}
.row.kind-verify .bar {
  background: #e0a83a;
}
.row.kind-answer .bar {
  background: #2a2a28;
}
.row.kind-map .bar {
  background: #b59243;
}

.meta {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  font-size: 11px;
  color: var(--ink-3);
}
.tok {
  color: var(--ink-3);
}

.footnote {
  margin: 12px 8px 0;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
  font-size: 10px;
  color: var(--ink-3);
  font-style: italic;
}
</style>
