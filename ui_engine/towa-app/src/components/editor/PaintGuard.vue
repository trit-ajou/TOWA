<script setup lang="ts">
// 그림 도구(brush/eraser/clone/fill) 활성 + 현재 active layer가 커스텀 그룹이 아닐 때
// 캔버스 영역에서의 좌클릭 mousedown을 잡아 안내 토스트만 띄움. 클릭 자체는 막지 않음
// — bitmappery interaction-pane이 자체적으로 paint를 무시하므로, 우리는 "왜 안 그려지는지"
// 만 사용자에게 알려주는 역할.
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
// @ts-expect-error bitmappery JS module
import ToolTypes from '@bitmappery/definitions/tool-types'
import type { Layer } from '@bitmappery/definitions/document'
import { classifyLayer, isPaintableLayer } from '@/utils/layer-classify'
import { useCanvasNotice } from '@/composables/useCanvasNotice'

const store = useStore()
const { showNotice } = useCanvasNotice()

const PAINT_TOOLS = new Set([
  ToolTypes.BRUSH, ToolTypes.ERASER, ToolTypes.CLONE, ToolTypes.FILL,
])

const activeTool = computed<string | null>(() => store.getters['bmp/activeTool'])
const activeLayer = computed<Layer | null>(() => {
  const doc = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  const idx = store.getters['bmp/activeLayerIndex'] as number | undefined
  if (!doc?.layers || idx === undefined) return null
  return doc.layers[idx] ?? null
})

const MESSAGES: Record<string, string> = {
  text: '텍스트 레이어에는 그림을 그릴 수 없습니다',
  original: '원본 레이어는 보호되어 있습니다 (커스텀 레이어를 추가하세요)',
}

function onMouseDown(e: MouseEvent) {
  if (e.button !== 0) return
  if (!activeTool.value || !PAINT_TOOLS.has(activeTool.value)) return
  const target = e.target as HTMLElement | null
  if (!target) return
  // bitmappery 캔버스 표면(.canvas-wrapper 내부)에서의 클릭만 paint 시도로 간주.
  // 캔버스 영역 위에 떠 있는 툴박스/오버레이 버튼 클릭은 제외.
  if (!target.closest('.canvas-wrapper')) return
  if (target.closest('button, input, select, textarea, [role="button"]')) return
  const layer = activeLayer.value
  if (!layer) return
  // 숨김 상태면 paint 자체가 보이지 않아 사용자가 "왜 안 그려지지"로 혼란 — 안내 우선
  if (!layer.visible) {
    showNotice('숨겨진 레이어에는 그림을 그릴 수 없습니다 (눈 아이콘으로 표시)')
    return
  }
  if (isPaintableLayer(layer)) return
  const group = classifyLayer(layer)
  showNotice(MESSAGES[group] ?? '이 레이어에는 그림을 그릴 수 없습니다')
}

onMounted(() => document.addEventListener('mousedown', onMouseDown, true))
onBeforeUnmount(() => document.removeEventListener('mousedown', onMouseDown, true))
</script>

<template><div style="display: none" /></template>
