<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, type CSSProperties } from 'vue'
import { useStore } from 'vuex'
import type { Layer } from '@bitmappery/definitions/document'
import { isTextLayer } from '@/utils/text-layer'
import type { LayerTextMeta } from '@/types/text-block'
// @ts-expect-error bitmappery JS module
import ToolTypes from '@bitmappery/definitions/tool-types'
// @ts-expect-error bitmappery JS module
import { LayerTypes } from '@bitmappery/definitions/layer-types'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'
// @ts-expect-error bitmappery JS module
import { getCanvasInstance } from '@bitmappery/services/canvas-service'

const store = useStore()

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

// Active only when text tool is selected and there is no fixed-mode text box
// currently selected — i.e. user is between blocks, ready to draw a new one.
const visible = computed(() => {
  if (activeTool.value !== ToolTypes.TEXT) return false
  const l = activeLayer.value
  if (!l) return true
  if (!isTextLayer(l)) return true
  const meta = (l.meta ?? {}) as Partial<LayerTextMeta>
  return meta.boxMode !== 'fixed'
})

// area geometry — matches canvas viewport area
interface ScreenRect { left: number; top: number; width: number; height: number }

const canvasRect = computed<ScreenRect | null>(() => {
  void tick.value
  if (!visible.value) return null
  const canvas = getCanvasInstance()
  if (!canvas) return null
  const area = document.getElementById('towa-canvas-area')
  if (!area) return null
  const canvasEl = canvas.getElement() as HTMLElement | null
  if (!canvasEl) return null
  const cRect = canvasEl.getBoundingClientRect()
  const aRect = area.getBoundingClientRect()
  return {
    left: cRect.left - aRect.left,
    top:  cRect.top  - aRect.top,
    width:  cRect.width,
    height: cRect.height,
  }
})

const areaStyle = computed<CSSProperties>(() => {
  const r = canvasRect.value
  if (!r) return { display: 'none' }
  return {
    left: `${r.left}px`,
    top: `${r.top}px`,
    width: `${r.width}px`,
    height: `${r.height}px`,
  }
})

// screen point → document coordinate
function pointToDoc(clientX: number, clientY: number): { x: number; y: number } | null {
  const canvas = getCanvasInstance()
  if (!canvas) return null
  const canvasEl = canvas.getElement() as HTMLElement | null
  if (!canvasEl) return null
  const cRect = canvasEl.getBoundingClientRect()
  const vp = canvas.getViewport() as { left: number; top: number }
  const zoom = canvas.zoomFactor as number
  return {
    x: (clientX - cRect.left) / zoom + vp.left,
    y: (clientY - cRect.top)  / zoom + vp.top,
  }
}

interface CreateState {
  startDoc: { x: number; y: number }
  current: { x: number; y: number }
  pointerId: number
  el: HTMLElement
  zoom: number
}
const create = ref<CreateState | null>(null)

const MIN_CREATE = 8

const previewStyle = computed<CSSProperties>(() => {
  const c = create.value
  const r = canvasRect.value
  const canvas = getCanvasInstance()
  if (!c || !r || !canvas) return { display: 'none' }
  const vp = canvas.getViewport() as { left: number; top: number }
  const zoom = canvas.zoomFactor as number
  const x1 = Math.min(c.startDoc.x, c.current.x)
  const y1 = Math.min(c.startDoc.y, c.current.y)
  const x2 = Math.max(c.startDoc.x, c.current.x)
  const y2 = Math.max(c.startDoc.y, c.current.y)
  // doc → area-local coords (area's own origin is at r.left/r.top inside towa-canvas-area)
  return {
    left: `${(x1 - vp.left) * zoom}px`,
    top:  `${(y1 - vp.top)  * zoom}px`,
    width:  `${(x2 - x1) * zoom}px`,
    height: `${(y2 - y1) * zoom}px`,
  }
})

function onPointerDown(event: PointerEvent) {
  if (event.button !== 0) return
  const docPoint = pointToDoc(event.clientX, event.clientY)
  const canvas = getCanvasInstance()
  if (!docPoint || !canvas) return
  event.preventDefault()
  event.stopPropagation()
  const el = event.currentTarget as HTMLElement
  el.setPointerCapture(event.pointerId)
  create.value = {
    startDoc: docPoint,
    current: docPoint,
    pointerId: event.pointerId,
    el,
    zoom: canvas.zoomFactor,
  }
}

function onPointerMove(event: PointerEvent) {
  const c = create.value
  if (!c) return
  const docPoint = pointToDoc(event.clientX, event.clientY)
  if (!docPoint) return
  c.current = docPoint
}

function onPointerUp(event: PointerEvent) {
  const c = create.value
  if (!c) return
  c.el.releasePointerCapture(c.pointerId)
  const width = Math.abs(c.current.x - c.startDoc.x)
  const height = Math.abs(c.current.y - c.startDoc.y)
  create.value = null
  event.preventDefault()
  event.stopPropagation()
  // Click without drag is a no-op (avoids accidental tiny boxes).
  if (width < MIN_CREATE || height < MIN_CREATE) return
  const left = Math.round(Math.min(c.startDoc.x, c.current.x))
  const top  = Math.round(Math.min(c.startDoc.y, c.current.y))
  const doc = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  if (!doc) return
  const layer = LayerFactory.create({
    type: LayerTypes.LAYER_TEXT,
    left,
    top,
    width: Math.round(width),
    height: Math.round(height),
    transparent: true,
    visible: true,
    text: {
      value: '',
      font: 'Noto Sans KR',
      size: 24,
      unit: 'px',
      lineHeight: 0,
      spacing: 0,
      color: '#000000',
      align: 'center',
      verticalAlign: 'middle',
    },
  }) as Layer
  ;(layer as Layer & { meta: LayerTextMeta }).meta = {
    blockId: layer.id,
    original: '',
    status: 'edited',
    boxMode: 'fixed',
  }
  store.commit('bmp/addLayer', layer)
  store.commit('editor/SELECT_LAYER', layer.id)
}
</script>

<template>
  <div
    v-if="visible && canvasRect"
    class="absolute"
    :style="areaStyle"
    style="z-index: 35;"
  >
    <div
      class="absolute inset-0"
      style="cursor: crosshair;"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
    />
    <div
      v-if="create"
      class="absolute border border-dashed border-towa-accent bg-towa-accent/10 pointer-events-none"
      :style="previewStyle"
    />
  </div>
</template>
