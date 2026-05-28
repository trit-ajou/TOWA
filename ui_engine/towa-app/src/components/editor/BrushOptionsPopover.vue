<script setup lang="ts">
// 캔버스 우클릭 시 현재 도구의 브러쉬 옵션(크기 + 종류)을 작은 popover로 노출.
// 대상: brush / clone / eraser. 그 외 도구는 우클릭을 가로채지 않아 기본 동작/다른 핸들러에 맡김.
// (zoom 도구는 ZoomToolHandler가 우클릭=줌아웃으로 점유.)
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
// @ts-expect-error bitmappery JS module
import ToolTypes from '@bitmappery/definitions/tool-types'
// @ts-expect-error bitmappery JS module
import BrushTypes from '@bitmappery/definitions/brush-types'

const store = useStore()
const activeTool = computed<string | null>(() => store.getters['bmp/activeTool'])

const SUPPORTED = [ToolTypes.BRUSH, ToolTypes.CLONE, ToolTypes.ERASER] as const
type SupportedTool = (typeof SUPPORTED)[number]

const optionsGetterByTool: Record<SupportedTool, string> = {
  [ToolTypes.BRUSH]: 'bmp/brushOptions',
  [ToolTypes.CLONE]: 'bmp/cloneOptions',
  [ToolTypes.ERASER]: 'bmp/eraserOptions',
}

const BRUSH_TYPE_LABELS: Array<{ value: number; label: string }> = [
  { value: BrushTypes.LINE, label: 'Line' },
  { value: BrushTypes.PAINT_BRUSH, label: 'Paint' },
  { value: BrushTypes.PEN, label: 'Pen' },
  { value: BrushTypes.CALLIGRAPHIC, label: 'Calligraphy' },
  { value: BrushTypes.CONNECTED, label: 'Connected' },
  { value: BrushTypes.NEAREST, label: 'Nearest' },
  { value: BrushTypes.SPRAY, label: 'Spray' },
]

const visible = ref(false)
const pos = ref({ x: 0, y: 0 })

const supportedTool = computed<SupportedTool | null>(() => {
  const t = activeTool.value
  return SUPPORTED.includes(t as SupportedTool) ? (t as SupportedTool) : null
})

const opts = computed<{ size: number; type: number; opacity?: number } | null>(() => {
  const tool = supportedTool.value
  if (!tool) return null
  return store.getters[optionsGetterByTool[tool]] ?? null
})

function setOption(option: 'size' | 'type' | 'opacity', value: number) {
  const tool = supportedTool.value
  if (!tool) return
  store.commit('bmp/setToolOptionValue', { tool, option, value })
}

function onContextMenu(e: MouseEvent) {
  // 캔버스 영역(#towa-canvas-area) 안 + 지원 도구일 때만 가로챔.
  const area = document.getElementById('towa-canvas-area')
  if (!area || !area.contains(e.target as Node)) return
  if (!supportedTool.value) return
  e.preventDefault()
  // 화면 우하단 가까우면 좌상단 방향으로 펼쳐 잘리지 않게.
  const POPOVER_W = 200
  const POPOVER_H = 160
  const vw = window.innerWidth
  const vh = window.innerHeight
  pos.value = {
    x: e.clientX + POPOVER_W < vw ? e.clientX : e.clientX - POPOVER_W,
    y: e.clientY + POPOVER_H < vh ? e.clientY : e.clientY - POPOVER_H,
  }
  visible.value = true
}

function onDocMouseDown(e: MouseEvent) {
  if (!visible.value) return
  const target = e.target as HTMLElement
  if (!target.closest('[data-brush-popover]')) visible.value = false
}

function onKeyDown(e: KeyboardEvent) {
  if (visible.value && e.key === 'Escape') {
    visible.value = false
    e.preventDefault()
  }
}

onMounted(() => {
  // capture 단계에서 잡아 bitmappery interaction-pane보다 먼저 동작.
  document.addEventListener('contextmenu', onContextMenu, true)
  document.addEventListener('mousedown', onDocMouseDown)
  window.addEventListener('keydown', onKeyDown)
})
onBeforeUnmount(() => {
  document.removeEventListener('contextmenu', onContextMenu, true)
  document.removeEventListener('mousedown', onDocMouseDown)
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible && opts"
      data-brush-popover
      class="fixed z-50 w-[200px] bg-towa-surface border border-towa-border rounded-md shadow-xl shadow-black/50 p-3 text-xs"
      :style="{ left: `${pos.x}px`, top: `${pos.y}px` }"
    >
      <div class="flex items-center justify-between mb-2">
        <span class="text-towa-text-muted">크기</span>
        <span class="text-towa-text tabular-nums">{{ opts.size }}px</span>
      </div>
      <input
        type="range"
        min="1"
        max="200"
        :value="opts.size"
        class="w-full accent-towa-accent mb-3"
        @input="(e) => setOption('size', Number((e.target as HTMLInputElement).value))"
      />
      <div class="text-towa-text-muted mb-1">종류</div>
      <div class="grid grid-cols-3 gap-1">
        <button
          v-for="bt in BRUSH_TYPE_LABELS"
          :key="bt.value"
          class="px-1.5 py-1 rounded text-[10px] transition-colors"
          :class="opts.type === bt.value
            ? 'bg-towa-accent text-white'
            : 'bg-towa-surface-light text-towa-text-muted hover:text-towa-text'"
          @click="setOption('type', bt.value)"
        >{{ bt.label }}</button>
      </div>
    </div>
  </Teleport>
</template>
