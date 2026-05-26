<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

// 우측 패널(도구 옵션 + 레이어) 사이 사용자 조절 splitter.
// 상단(ToolOptionsPanel) 높이를 px 단위로 유지. localStorage에 영속화.

const STORAGE_KEY = 'towa.detail-editor.options-panel-height'
const DEFAULT_HEIGHT = 200
const MIN_HEIGHT = 80
const MIN_BOTTOM = 120 // LayerPanel 최소 높이

function loadInitial(): number {
  const raw = typeof window !== 'undefined' ? window.localStorage.getItem(STORAGE_KEY) : null
  const v = raw ? Number(raw) : NaN
  return Number.isFinite(v) && v >= MIN_HEIGHT ? v : DEFAULT_HEIGHT
}

const topHeight = ref(loadInitial())
const containerRef = ref<HTMLElement | null>(null)
const dragging = ref(false)
let startY = 0
let startHeight = 0

function onPointerDown(e: PointerEvent) {
  dragging.value = true
  startY = e.clientY
  startHeight = topHeight.value
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}
function onPointerMove(e: PointerEvent) {
  if (!dragging.value) return
  const container = containerRef.value
  if (!container) return
  const containerHeight = container.clientHeight
  const next = startHeight + (e.clientY - startY)
  const maxTop = containerHeight - MIN_BOTTOM
  topHeight.value = Math.max(MIN_HEIGHT, Math.min(maxTop, next))
}
function onPointerUp(e: PointerEvent) {
  if (!dragging.value) return
  dragging.value = false
  ;(e.currentTarget as HTMLElement).releasePointerCapture?.(e.pointerId)
  window.localStorage.setItem(STORAGE_KEY, String(Math.round(topHeight.value)))
}

// 컨테이너 크기가 줄어들면 MIN_BOTTOM 확보 위해 topHeight 클램프
let ro: ResizeObserver | null = null
onMounted(() => {
  if (!containerRef.value || typeof ResizeObserver === 'undefined') return
  ro = new ResizeObserver(() => {
    const container = containerRef.value
    if (!container) return
    const maxTop = container.clientHeight - MIN_BOTTOM
    if (topHeight.value > maxTop) topHeight.value = Math.max(MIN_HEIGHT, maxTop)
  })
  ro.observe(containerRef.value)
})
onBeforeUnmount(() => ro?.disconnect())
</script>

<template>
  <div ref="containerRef" class="w-64 h-full flex flex-col">
    <div class="shrink-0 overflow-hidden" :style="{ height: `${topHeight}px` }">
      <slot name="top" />
    </div>

    <!-- splitter handle -->
    <div
      class="shrink-0 h-1.5 cursor-row-resize bg-towa-border hover:bg-towa-accent transition-colors relative group"
      :class="{ '!bg-towa-accent': dragging }"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
    >
      <!-- 가운데 grip 표시 -->
      <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 flex justify-center pointer-events-none">
        <div class="w-8 h-0.5 rounded bg-towa-text-muted/50 group-hover:bg-white/80" />
      </div>
    </div>

    <div class="flex-1 min-h-0 overflow-hidden">
      <slot name="bottom" />
    </div>
  </div>
</template>
