<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, type CSSProperties } from 'vue'
import { useStore } from 'vuex'
import type { Layer } from '@bitmappery/definitions/document'
import { getTextMeta, isTextLayer } from '@/utils/text-layer'
// @ts-expect-error bitmappery JS module
import ToolTypes from '@bitmappery/definitions/tool-types'
// @ts-expect-error bitmappery JS module
import { getCanvasInstance } from '@bitmappery/services/canvas-service'
// @ts-expect-error bitmappery JS module
import { getRendererForLayer } from '@bitmappery/factories/renderer-factory'
// @ts-expect-error bitmappery JS module
import { clearCacheProperty } from '@bitmappery/rendering/cache/bitmap-cache'
// @ts-expect-error bitmappery JS module
import { enqueueState } from '@bitmappery/factories/history-state-factory'

interface BoxGeom { left: number; top: number; width: number; height: number }

function findLayerIndexById(id: string): number {
  const doc = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  return doc?.layers?.findIndex((l) => l.id === id) ?? -1
}

function applyBoxToLayer(layerId: string, box: BoxGeom) {
  const idx = findLayerIndexById(layerId)
  if (idx < 0) return
  const doc = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  const layer = doc?.layers?.[idx]
  if (!layer) return
  const sizeChanged = layer.width !== box.width || layer.height !== box.height
  store.commit('bmp/updateLayer', { index: idx, opts: { ...box } })
  const renderer = getRendererForLayer({ id: layerId })
  if (renderer) {
    renderer.syncPosition?.()
    if (sizeChanged && isTextLayer(layer)) {
      clearCacheProperty(layer, 'textBitmap')
      clearCacheProperty(layer, 'text')
      renderer.resetFilterAndRecache?.()
    }
  }
}

const store = useStore()

// rAF tick to follow canvas viewport/zoom changes (canvas state lives on the
// zCanvas instance, not in Vuex, so reactivity needs an external pulse).
const tick = ref(0)
let rafId = 0
function loop() {
  tick.value = (tick.value + 1) | 0
  rafId = requestAnimationFrame(loop)
}
onMounted(() => { rafId = requestAnimationFrame(loop) })
onBeforeUnmount(() => cancelAnimationFrame(rafId))

const activeTool = computed<string | null>(() => store.getters['bmp/activeTool'] ?? null)
const activeLayer = computed<Layer | null>(() => store.getters['bmp/activeLayer'] ?? null)
const activeLayerIndex = computed<number>(() => {
  const doc = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  const id = activeLayer.value?.id
  return id && doc?.layers ? doc.layers.findIndex((l) => l.id === id) : -1
})

const visible = computed(() => {
  const layer = activeLayer.value
  if (!layer || !isTextLayer(layer)) return false
  const meta = getTextMeta(layer)
  if (meta?.boxMode !== 'fixed') return false
  return activeTool.value === ToolTypes.TEXT
})

interface ScreenBox { left: number; top: number; width: number; height: number }

const box = computed<ScreenBox | null>(() => {
  void tick.value
  if (!visible.value) return null
  const canvas = getCanvasInstance()
  const layer = activeLayer.value
  if (!canvas || !layer) return null
  const area = document.getElementById('towa-canvas-area')
  if (!area) return null
  const canvasEl = canvas.getElement() as HTMLElement | null
  if (!canvasEl) return null
  const cRect = canvasEl.getBoundingClientRect()
  const aRect = area.getBoundingClientRect()
  const vp = canvas.getViewport() as { left: number; top: number }
  const zoom = canvas.zoomFactor as number
  return {
    left: (cRect.left - aRect.left) + (layer.left - vp.left) * zoom,
    top:  (cRect.top  - aRect.top)  + (layer.top  - vp.top)  * zoom,
    width:  layer.width  * zoom,
    height: layer.height * zoom,
  }
})

const boxStyle = computed<CSSProperties>(() => {
  const b = box.value
  if (!b) return { display: 'none' }
  return {
    left: `${b.left}px`,
    top: `${b.top}px`,
    width: `${b.width}px`,
    height: `${b.height}px`,
  }
})

type Handle = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w' | 'move'

const HANDLES: Array<{ id: Exclude<Handle, 'move'>; style: CSSProperties; cursor: string }> = [
  { id: 'nw', style: { top: '0%',  left: '0%',   transform: 'translate(-50%, -50%)' }, cursor: 'nwse-resize' },
  { id: 'n',  style: { top: '0%',  left: '50%',  transform: 'translate(-50%, -50%)' }, cursor: 'ns-resize'   },
  { id: 'ne', style: { top: '0%',  left: '100%', transform: 'translate(-50%, -50%)' }, cursor: 'nesw-resize' },
  { id: 'e',  style: { top: '50%', left: '100%', transform: 'translate(-50%, -50%)' }, cursor: 'ew-resize'   },
  { id: 'se', style: { top: '100%',left: '100%', transform: 'translate(-50%, -50%)' }, cursor: 'nwse-resize' },
  { id: 's',  style: { top: '100%',left: '50%',  transform: 'translate(-50%, -50%)' }, cursor: 'ns-resize'   },
  { id: 'sw', style: { top: '100%',left: '0%',   transform: 'translate(-50%, -50%)' }, cursor: 'nesw-resize' },
  { id: 'w',  style: { top: '50%', left: '0%',   transform: 'translate(-50%, -50%)' }, cursor: 'ew-resize'   },
]

interface DragState {
  mode: Handle
  layerId: string
  startPointer: { x: number; y: number }
  startBox: BoxGeom
  finalBox: BoxGeom
  zoom: number
  pointerId: number
  el: HTMLElement
  moved: boolean
}
let drag: DragState | null = null

const MIN_SIZE = 8

function onPointerDown(event: PointerEvent, mode: Handle) {
  const layer = activeLayer.value
  const canvas = getCanvasInstance()
  if (!layer || !canvas) return
  event.preventDefault()
  event.stopPropagation()
  const el = event.currentTarget as HTMLElement
  el.setPointerCapture(event.pointerId)
  const startBox = { left: layer.left, top: layer.top, width: layer.width, height: layer.height }
  drag = {
    mode,
    layerId: layer.id,
    startPointer: { x: event.clientX, y: event.clientY },
    startBox,
    finalBox: { ...startBox },
    zoom: canvas.zoomFactor,
    pointerId: event.pointerId,
    el,
    moved: false,
  }
}

function onPointerMove(event: PointerEvent) {
  if (!drag) return
  const dx = (event.clientX - drag.startPointer.x) / drag.zoom
  const dy = (event.clientY - drag.startPointer.y) / drag.zoom
  if (!drag.moved && (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5)) drag.moved = true
  const { startBox, mode } = drag
  let { left, top, width, height } = startBox
  if (mode === 'move') {
    left = startBox.left + dx
    top  = startBox.top  + dy
  } else {
    if (mode.includes('w')) {
      const w = Math.max(MIN_SIZE, startBox.width - dx)
      left = startBox.left + (startBox.width - w)
      width = w
    } else if (mode.includes('e')) {
      width = Math.max(MIN_SIZE, startBox.width + dx)
    }
    if (mode.includes('n')) {
      const h = Math.max(MIN_SIZE, startBox.height - dy)
      top = startBox.top + (startBox.height - h)
      height = h
    } else if (mode.includes('s')) {
      height = Math.max(MIN_SIZE, startBox.height + dy)
    }
  }
  drag.finalBox = {
    left: Math.round(left),
    top: Math.round(top),
    width: Math.round(width),
    height: Math.round(height),
  }
  applyBoxToLayer(drag.layerId, drag.finalBox)
}

function onPointerUp(event: PointerEvent) {
  if (!drag) return
  drag.el.releasePointerCapture(drag.pointerId)
  const { layerId, startBox, finalBox, moved } = drag
  drag = null
  event.preventDefault()
  event.stopPropagation()
  // single history entry per drag operation — undo restores box at drag start.
  if (moved) {
    enqueueState(`textbox-geom-${layerId}`, {
      undo: () => applyBoxToLayer(layerId, startBox),
      redo: () => applyBoxToLayer(layerId, finalBox),
    })
  }
}

function onBoxDoubleClick(event: MouseEvent) {
  // Double-click inside the box → focus the corresponding block's textarea
  // in the side panel (TOWA's text editing path is panel-driven).
  const layer = activeLayer.value
  if (!layer) return
  event.preventDefault()
  event.stopPropagation()
  requestAnimationFrame(() => {
    const el = document.querySelector(
      `[data-text-block-id="${layer.id}"] textarea`,
    ) as HTMLTextAreaElement | null
    el?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    el?.focus()
  })
}
</script>

<template>
  <div
    v-if="visible && box"
    class="absolute"
    :style="boxStyle"
    style="z-index: 40; pointer-events: none;"
  >
    <!--
      Box body = move-drag zone + double-click target for text editing.
      Single click drag → move; double click → focus panel textarea (TOWA's
      text editing path is panel-driven).
    -->
    <div
      class="absolute inset-0 border border-towa-accent"
      style="pointer-events: auto; cursor: move;"
      @pointerdown="onPointerDown($event, 'move')"
      @dblclick="onBoxDoubleClick"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
    />
    <!-- resize handles -->
    <div
      v-for="h in HANDLES"
      :key="h.id"
      class="absolute w-2.5 h-2.5 bg-white border border-towa-accent"
      :style="{ ...h.style, cursor: h.cursor, pointerEvents: 'auto' }"
      @pointerdown="onPointerDown($event, h.id)"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
    />
  </div>
</template>
