<script setup lang="ts">
// Zoom 도구 [Z]: 캔버스 위에 transparent overlay를 띄워 클릭/드래그/우클릭을 가로채 신규 줌 동작 구현.
//
// 스펙 (canvas_ui_specs.md):
//   - 좌클릭: 고정치 줌인 (×1.25에 해당하는 1단계)
//   - 우클릭: 고정치 줌아웃 (×0.8에 해당하는 1단계)
//   - 드래그: 클릭 위치에서 화면 중심을 향하는 방향이면 줌인, 반대면 줌아웃 (거리 비례)
//
// bitmappery zoom level은 MIN_ZOOM(-50) ~ MAX_ZOOM(+50) 정수. base = 0.
// `bmp/setToolOptionValue` 로 'level' 옵션을 직접 commit 하면 캔버스가 반응.

import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
// @ts-expect-error bitmappery JS module
import ToolTypes, { MIN_ZOOM, MAX_ZOOM } from '@bitmappery/definitions/tool-types'
import { getCanvasInstance } from '@bitmappery/services/canvas-service'

const store = useStore()
const activeTool = computed<string | null>(() => store.getters['bmp/activeTool'])
const zoomLevel = computed<number>(() => store.getters['bmp/zoomOptions']?.level ?? 0)
const isActive = computed(() => activeTool.value === ToolTypes.ZOOM)

const STEP = 5            // 클릭 1회당 level 변화량 (≈ ×1.25)
const DRAG_GAIN = 0.15    // 1px 드래그당 level 변화량 (조정 가능)
const CLICK_THRESHOLD = 4 // 픽셀 이내 이동이면 클릭으로 간주

function setLevel(next: number) {
  const clamped = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, next))
  store.commit('bmp/setToolOptionValue', { tool: ToolTypes.ZOOM, option: 'level', value: clamped })
}

// 클라이언트(뷰포트) 좌표를 anchor로 zoom 적용. anchor는 bitmappery store에 임시 저장되고
// document-canvas의 zoom watch에서 setDocumentScale에 전달되어 한 호출 안에 zoom+pan 처리된다.
function setLevelAt(next: number, clientX: number, clientY: number) {
  const canvas = getCanvasInstance() as unknown as { getElement(): HTMLCanvasElement } | null
  const el = canvas?.getElement?.()
  if (el) {
    const rect = el.getBoundingClientRect()
    const localX = clientX - rect.left
    const localY = clientY - rect.top
    // 클릭이 캔버스 영역 안에 있을 때만 anchor 적용. 캔버스 밖 클릭은 기본 동작(centered).
    if (localX >= 0 && localX <= rect.width && localY >= 0 && localY <= rect.height) {
      store.commit('bmp/setPendingZoomAnchor', { localX, localY })
    }
  }
  setLevel(next)
}

// Photoshop scrubby zoom: anchor는 시작 클릭 위치 고정, 수평 드래그(dx)로 줌 정도 결정 (우=줌인 / 좌=줌아웃).
interface DragState {
  pointerId: number
  startX: number              // overlay 좌표 (dx 계산용)
  startClientX: number; startClientY: number  // 화면 좌표 (줌 anchor)
  startLevel: number
}
const drag = ref<DragState | null>(null)
const moved = ref(false)

function onPointerDown(e: PointerEvent) {
  if (!isActive.value) return
  if (e.button !== 0 && e.button !== 2) return // 좌·우 클릭만
  e.preventDefault()

  // 우클릭: 즉시 줌아웃 (클릭 위치 기준)
  if (e.button === 2) {
    setLevelAt(zoomLevel.value - STEP, e.clientX, e.clientY)
    return
  }

  const overlay = e.currentTarget as HTMLElement
  drag.value = {
    pointerId: e.pointerId,
    startX: e.clientX,
    startClientX: e.clientX, startClientY: e.clientY,
    startLevel: zoomLevel.value,
  }
  moved.value = false
  overlay.setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  const d = drag.value
  if (!d || e.pointerId !== d.pointerId) return
  // Photoshop scrubby zoom: 수평 dx만 사용. 우=줌인, 좌=줌아웃. anchor는 시작 클릭 위치 고정.
  const dx = e.clientX - d.startX
  if (Math.abs(dx) > CLICK_THRESHOLD) moved.value = true
  setLevelAt(d.startLevel + dx * DRAG_GAIN, d.startClientX, d.startClientY)
}

function onPointerUp(e: PointerEvent) {
  const d = drag.value
  if (!d || e.pointerId !== d.pointerId) return
  const overlay = e.currentTarget as HTMLElement
  overlay.releasePointerCapture?.(e.pointerId)
  // 드래그 이동이 거의 없으면 클릭으로 간주 → 클릭 위치 기준 줌인
  if (!moved.value) {
    setLevelAt(d.startLevel + STEP, d.startClientX, d.startClientY)
  }
  drag.value = null
}

function onContextMenu(e: MouseEvent) {
  if (isActive.value) e.preventDefault() // 우클릭 기본 메뉴 차단
}

// ─── Wheel / 핀치 줌 (도구 무관, 캔버스 영역 안에서만) ───
// 터치패드 핀치는 wheel + ctrlKey=true 로 들어옴 (브라우저 페이지 줌 트리거).
// 일반 휠은 zoom 도구가 active일 때만 줌으로 가로채 다른 도구일 때 스크롤 막지 않음.
const WHEEL_STEP = 2
function onWheel(e: WheelEvent) {
  const area = document.getElementById('towa-canvas-area')
  if (!area || !area.contains(e.target as Node)) return
  const isPinch = e.ctrlKey || e.metaKey
  const wantsZoom = isPinch || isActive.value
  if (!wantsZoom) return
  e.preventDefault()
  // deltaY < 0 (위로 휠 / 핀치 아웃) → 줌인. 줌 기준점 = 커서 위치.
  const dir = e.deltaY < 0 ? 1 : -1
  setLevelAt(zoomLevel.value + dir * WHEEL_STEP, e.clientX, e.clientY)
}
onMounted(() => window.addEventListener('wheel', onWheel, { passive: false }))
onBeforeUnmount(() => window.removeEventListener('wheel', onWheel))
</script>

<template>
  <div
    v-if="isActive"
    class="absolute inset-0 z-20"
    style="cursor: zoom-in"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
    @contextmenu="onContextMenu"
  />
</template>
