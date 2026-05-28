<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, type CSSProperties } from 'vue'
import { useStore } from 'vuex'
import type { Layer } from '@bitmappery/definitions/document'
import { getTextMeta, isTextLayer } from '@/utils/text-layer'
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

// Always-on interaction layer for the text tool. TextBoxOverlay sits on top
// (z=40) and captures pointer events inside the selected box; this layer
// (z=35) handles everything else: clicks on other boxes (select), clicks on
// empty area (deselect), and empty-area drag (create new box).
const visible = computed(() => activeTool.value === ToolTypes.TEXT && !!store.getters['bmp/activeDocument'])

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

interface PointerState {
  startDoc: { x: number; y: number }
  current: { x: number; y: number }
  pointerId: number
  el: HTMLElement
  zoom: number
  hitLayer: Layer | null   // if pointerdown landed inside an existing text box
  moved: boolean
}
const pointer = ref<PointerState | null>(null)
const create = computed<PointerState | null>(() => {
  const p = pointer.value
  if (!p || !p.moved || p.hitLayer) return null
  return p
})

const MIN_CREATE = 8
const DRAG_THRESHOLD = 3 // doc-space pixels

function hitTestTextLayer(doc: { x: number; y: number }): Layer | null {
  const ad = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  const layers = ad?.layers ?? []
  // top-down for z-order respect
  for (let i = layers.length - 1; i >= 0; i--) {
    const l = layers[i]
    if (!isTextLayer(l)) continue
    const meta = getTextMeta(l)
    if (meta?.boxMode !== 'fixed') continue
    if (
      doc.x >= l.left &&
      doc.x <= l.left + l.width &&
      doc.y >= l.top &&
      doc.y <= l.top + l.height
    ) {
      return l
    }
  }
  return null
}

function selectLayer(layerId: string) {
  const ad = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  const idx = ad?.layers?.findIndex((l) => l.id === layerId) ?? -1
  if (idx < 0) return
  store.commit('editor/SELECT_LAYER', layerId)
  store.commit('bmp/setActiveLayerIndex', idx)
}

function deselect() {
  store.commit('editor/SELECT_LAYER', null)
  store.commit('bmp/setActiveLayerIndex', -1)
}

function focusBlockTextarea(layerId: string) {
  nextTick(() => {
    const el = document.querySelector(
      `[data-text-block-id="${layerId}"] textarea`,
    ) as HTMLTextAreaElement | null
    el?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    el?.focus()
  })
}

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
  pointer.value = {
    startDoc: docPoint,
    current: docPoint,
    pointerId: event.pointerId,
    el,
    zoom: canvas.zoomFactor,
    hitLayer: hitTestTextLayer(docPoint),
    moved: false,
  }
}

function onPointerMove(event: PointerEvent) {
  const p = pointer.value
  if (!p) return
  const docPoint = pointToDoc(event.clientX, event.clientY)
  if (!docPoint) return
  p.current = docPoint
  if (!p.moved) {
    if (
      Math.abs(docPoint.x - p.startDoc.x) > DRAG_THRESHOLD ||
      Math.abs(docPoint.y - p.startDoc.y) > DRAG_THRESHOLD
    ) {
      p.moved = true
    }
  }
}

function onPointerUp(event: PointerEvent) {
  const p = pointer.value
  if (!p) return
  p.el.releasePointerCapture(p.pointerId)
  pointer.value = null
  event.preventDefault()
  event.stopPropagation()

  // click (no drag): select the box under the pointer, or deselect if empty
  if (!p.moved) {
    if (p.hitLayer) selectLayer(p.hitLayer.id)
    else deselect()
    return
  }

  // drag started inside an existing box → do nothing (TextBoxOverlay handles
  // dragging selected boxes; this overlay only catches the gap when no box
  // is selected, so we just ignore drags on other boxes here)
  if (p.hitLayer) {
    selectLayer(p.hitLayer.id)
    return
  }

  // drag in empty area → create new text box
  const width = Math.abs(p.current.x - p.startDoc.x)
  const height = Math.abs(p.current.y - p.startDoc.y)
  if (width < MIN_CREATE || height < MIN_CREATE) return
  const left = Math.round(Math.min(p.startDoc.x, p.current.x))
  const top  = Math.round(Math.min(p.startDoc.y, p.current.y))
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
  // bmp/addLayer auto-sets activeLayerIndex; mirror it in TOWA editor state
  // and immediately focus the panel textarea so the user can start typing.
  store.commit('editor/SELECT_LAYER', layer.id)
  focusBlockTextarea(layer.id)
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
