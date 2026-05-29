<script setup lang="ts">
// Alt+드래그 색 추출 — 포토샵 스타일.
// 흐름:
//   Alt down (캔버스 위) → 커서가 스포이드로 바뀜
//   Alt+mousedown → 확대 미리보기(돋보기 원 + 색 ring) 표시 시작
//   Alt+mousemove (드래그) → 미리보기 위치/색 실시간 갱신
//   Alt+mouseup → 그 시점 색이 전경색(bmp/activeColor)으로 확정
//   ESC 또는 Alt up 도중 → 미리보기 닫고 색 확정 안 함
//
// CLONE 도구는 Alt+클릭이 source 샘플링과 겹치므로 양보.
import { computed, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { useStore } from 'vuex'
// @ts-expect-error bitmappery JS module
import ToolTypes from '@bitmappery/definitions/tool-types'
import { getCanvasInstance } from '@bitmappery/services/canvas-service'

const store = useStore()
const activeTool = computed<string | null>(() => store.getters['bmp/activeTool'])

const PREVIEW_RADIUS = 50            // 외곽 원 반지름 (px)
const RING_THICKNESS = 8             // 색 표시 ring 두께 (px)
const ZOOM_GRID = 13                 // 한 변당 픽셀 수 (홀수 권장 — 중앙 픽셀 1개)
const ZOOM_PX = (PREVIEW_RADIUS - RING_THICKNESS) * 2  // 내부 zoom 영역 크기

const altDown = ref(false)
const dragging = ref(false)
const preview = reactive({
  cssX: 0,
  cssY: 0,
  color: '#000000',
  inside: false,
})
const zoomCanvas = ref<HTMLCanvasElement | null>(null)

function rgbaToHex(r: number, g: number, b: number): string {
  const h = (n: number) => n.toString(16).padStart(2, '0')
  return `#${h(r)}${h(g)}${h(b)}`
}

function getCanvasEl(): HTMLCanvasElement | null {
  const c = getCanvasInstance() as unknown as { getElement(): HTMLCanvasElement } | null
  return c?.getElement?.() ?? null
}

function isOverCanvasArea(target: EventTarget | null): boolean {
  const area = document.getElementById('towa-canvas-area')
  return !!(area && target instanceof Node && area.contains(target))
}

// CSS 좌표(viewport) → canvas internal pixel 좌표
function cssToCanvasPixel(el: HTMLCanvasElement, clientX: number, clientY: number) {
  const rect = el.getBoundingClientRect()
  if (clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom) {
    return null
  }
  const x = Math.floor(((clientX - rect.left) / rect.width) * el.width)
  const y = Math.floor(((clientY - rect.top) / rect.height) * el.height)
  return { x, y }
}

function sampleAndRender(clientX: number, clientY: number) {
  const el = getCanvasEl()
  if (!el) return
  const pix = cssToCanvasPixel(el, clientX, clientY)
  if (!pix) {
    preview.inside = false
    return
  }
  const ctx = el.getContext('2d', { willReadFrequently: true })
  if (!ctx) return

  // 중앙 픽셀 색
  try {
    const center = ctx.getImageData(pix.x, pix.y, 1, 1).data
    preview.color = rgbaToHex(center[0], center[1], center[2])
  } catch {
    return
  }

  // 확대 미리보기: 주변 ZOOM_GRID x ZOOM_GRID 영역을 zoom canvas에 nearest-neighbor 확대
  const half = Math.floor(ZOOM_GRID / 2)
  const sx = Math.max(0, Math.min(el.width - ZOOM_GRID, pix.x - half))
  const sy = Math.max(0, Math.min(el.height - ZOOM_GRID, pix.y - half))
  const z = zoomCanvas.value
  if (z) {
    const zctx = z.getContext('2d')
    if (zctx) {
      zctx.imageSmoothingEnabled = false
      zctx.clearRect(0, 0, z.width, z.height)
      zctx.drawImage(el, sx, sy, ZOOM_GRID, ZOOM_GRID, 0, 0, z.width, z.height)
    }
  }

  preview.cssX = clientX
  preview.cssY = clientY
  preview.inside = true
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key !== 'Alt') return
  if (activeTool.value === ToolTypes.CLONE) return
  altDown.value = true
}

function onKeyUp(e: KeyboardEvent) {
  if (e.key !== 'Alt') return
  // 드래그 중에 Alt 떼면 색 확정 없이 취소
  if (dragging.value) {
    dragging.value = false
    preview.inside = false
  }
  altDown.value = false
}

function onMouseDown(e: MouseEvent) {
  if (!e.altKey) return
  if (e.button !== 0) return
  if (activeTool.value === ToolTypes.CLONE) return
  if (!isOverCanvasArea(e.target)) return
  // bitmappery가 같은 mousedown을 처리하지 않도록 차단
  e.preventDefault()
  e.stopPropagation()
  dragging.value = true
  sampleAndRender(e.clientX, e.clientY)
}

function onMouseMove(e: MouseEvent) {
  if (!altDown.value) return
  if (!dragging.value) {
    // 드래그 전엔 커서만 스포이드 — 미리보기 안 띄움
    return
  }
  sampleAndRender(e.clientX, e.clientY)
}

function onMouseUp(e: MouseEvent) {
  if (!dragging.value) return
  e.preventDefault()
  e.stopPropagation()
  // 최종 위치에서 한 번 더 샘플링한 색으로 전경색 확정
  sampleAndRender(e.clientX, e.clientY)
  if (preview.inside) {
    store.commit('bmp/setActiveColor', preview.color)
  }
  dragging.value = false
  preview.inside = false
}

function onKeyDownEsc(e: KeyboardEvent) {
  if (e.key === 'Escape' && dragging.value) {
    dragging.value = false
    preview.inside = false
  }
}

const cursorStyle = computed(() => (altDown.value && activeTool.value !== ToolTypes.CLONE ? 'crosshair' : ''))

// Alt 동안 캔버스 영역 전체에 스포이드 커서 적용. body class로 토글하는 게 가장 단순.
function applyCursorClass(on: boolean) {
  const area = document.getElementById('towa-canvas-area')
  if (!area) return
  if (on) area.classList.add('eyedropper-cursor')
  else area.classList.remove('eyedropper-cursor')
}

import { watch } from 'vue'
watch([altDown, activeTool], ([alt, tool]) => {
  applyCursorClass(alt && tool !== ToolTypes.CLONE)
})

onMounted(() => {
  document.addEventListener('keydown', onKeyDown)
  document.addEventListener('keydown', onKeyDownEsc)
  document.addEventListener('keyup', onKeyUp)
  document.addEventListener('mousedown', onMouseDown, true)
  document.addEventListener('mousemove', onMouseMove, true)
  document.addEventListener('mouseup', onMouseUp, true)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeyDown)
  document.removeEventListener('keydown', onKeyDownEsc)
  document.removeEventListener('keyup', onKeyUp)
  document.removeEventListener('mousedown', onMouseDown, true)
  document.removeEventListener('mousemove', onMouseMove, true)
  document.removeEventListener('mouseup', onMouseUp, true)
  applyCursorClass(false)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="dragging && preview.inside"
      class="fixed pointer-events-none z-[100] rounded-full shadow-lg shadow-black/40"
      :style="{
        left: (preview.cssX - PREVIEW_RADIUS) + 'px',
        top: (preview.cssY - PREVIEW_RADIUS) + 'px',
        width: (PREVIEW_RADIUS * 2) + 'px',
        height: (PREVIEW_RADIUS * 2) + 'px',
        background: preview.color,
        // 안쪽 zoom canvas 컨테이너용 내부 패딩
        padding: RING_THICKNESS + 'px',
        boxSizing: 'border-box',
        outline: '1px solid rgba(0,0,0,0.6)',
      }"
    >
      <canvas
        ref="zoomCanvas"
        :width="ZOOM_PX"
        :height="ZOOM_PX"
        class="rounded-full block"
        :style="{ width: ZOOM_PX + 'px', height: ZOOM_PX + 'px', background: '#000' }"
      />
      <!-- 중앙 픽셀을 가리키는 작은 crosshair -->
      <div
        class="absolute pointer-events-none"
        :style="{
          left: '50%', top: '50%',
          width: (ZOOM_PX / ZOOM_GRID) + 'px',
          height: (ZOOM_PX / ZOOM_GRID) + 'px',
          transform: 'translate(-50%, -50%)',
          border: '1px solid #fff',
          boxShadow: '0 0 0 1px rgba(0,0,0,0.7)',
        }"
      />
    </div>
  </Teleport>
</template>

<style>
.eyedropper-cursor,
.eyedropper-cursor * {
  cursor: crosshair !important;
}
</style>
