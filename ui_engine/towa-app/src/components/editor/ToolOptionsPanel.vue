<script setup lang="ts">
import { computed } from 'vue'
import { useStore } from 'vuex'
import { Plus, Trash2 } from 'lucide-vue-next'
import TextLayerInspector from './TextLayerInspector.vue'
import type { Layer } from '@bitmappery/definitions/document'
import { LayerTypes } from '@bitmappery/definitions/layer-types'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'
// @ts-expect-error bitmappery JS module
import ToolTypes from '@bitmappery/definitions/tool-types'
import { isTextLayer } from '@/utils/text-layer'
import { useAutoSave } from '@/composables/useAutoSave'

const store = useStore()
const { markDirty } = useAutoSave()

const activeTool = computed<string | null>(() => store.getters['bmp/activeTool'])
const activeToolOptions = computed<Record<string, unknown> | undefined>(() => store.getters['bmp/activeToolOptions'])
const isText = computed(() => activeTool.value === 'text')

// 선택된 레이어가 텍스트일 때만 삭제 버튼 활성
const activeTextLayer = computed<Layer | null>(() => {
  const layer = store.getters['bmp/activeLayer'] as Layer | undefined
  return layer && isTextLayer(layer) ? layer : null
})

const TOOL_LABELS: Record<string, string> = {
  move: '화면 이동', drag: '객체 이동', zoom: '줌',
  selection: '사각 선택', wand: '마법사 선택', lasso: '올가미',
  brush: '브러쉬', clone: '도장', eraser: '지우개',
  fill: '페인트 통', eyedropper: '스포이드',
  text: '텍스트', rotate: '회전', scale: '변형', mirror: '미러',
}

const label = computed(() => activeTool.value ? (TOOL_LABELS[activeTool.value] ?? activeTool.value) : '도구 미선택')

// 브러쉬 계열 (브러쉬/지우개/도장) 공통 옵션 노출
const isBrushLike = computed(() =>
  activeTool.value === 'brush' || activeTool.value === 'eraser' || activeTool.value === 'clone'
)

const brushSize = computed<number>({
  get: () => Number(activeToolOptions.value?.size ?? 10),
  set: (value) => store.commit('bmp/setToolOptionValue', { tool: activeTool.value, option: 'size', value }),
})

const brushOpacity = computed<number>({
  get: () => Number(activeToolOptions.value?.opacity ?? 1),
  set: (value) => store.commit('bmp/setToolOptionValue', { tool: activeTool.value, option: 'opacity', value }),
})

// 텍스트 레이어 추가/삭제는 패널 레벨 동작이므로 헤더에서 다룬다.
function addTextLayer() {
  const doc = store.getters['bmp/activeDocument'] as { width?: number; height?: number; layers?: Layer[] } | undefined
  if (!doc) return
  const docW = doc.width ?? 800
  const docH = doc.height ?? 1200
  const width = Math.max(120, Math.min(300, Math.round(docW * 0.25)))
  const height = Math.max(60, Math.round(width * 0.4))
  const left = Math.round((docW - width) / 2)
  const top = Math.round((docH - height) / 2)
  const layer = LayerFactory.create({
    type: LayerTypes.LAYER_TEXT,
    left, top, width, height,
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
  layer.meta = { blockId: layer.id, original: '', status: 'edited', boxMode: 'fixed' }
  store.commit('bmp/addLayer', layer)
  store.commit('editor/SELECT_LAYER', layer.id)
  store.commit('bmp/setActiveTool', { tool: ToolTypes.TEXT, document: doc })
  markDirty()
}

function removeTextLayer() {
  const index = store.getters['bmp/activeLayerIndex'] ?? -1
  if (index < 0 || !activeTextLayer.value) return
  store.commit('bmp/removeLayer', index)
  store.commit('editor/SELECT_LAYER', null)
  markDirty()
}
</script>

<template>
  <aside class="w-full h-full bg-towa-surface border-l border-towa-border flex flex-col">
    <header class="px-3 py-2 border-b border-towa-border flex items-start justify-between gap-2">
      <div>
        <div class="text-xs uppercase tracking-wider font-semibold text-towa-accent">도구 옵션</div>
        <div class="text-sm font-medium text-towa-text mt-0.5">{{ label }}</div>
      </div>
      <div v-if="isText" class="flex items-center gap-0.5 pt-0.5">
        <button
          class="p-1 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-accent transition-colors"
          title="텍스트 블록 추가"
          @click="addTextLayer"
        >
          <Plus :size="14" />
        </button>
        <button
          class="p-1 rounded text-towa-text-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed hover:bg-red-500/20 hover:text-red-400"
          title="선택한 텍스트 블록 삭제"
          :disabled="!activeTextLayer"
          @click="removeTextLayer"
        >
          <Trash2 :size="14" />
        </button>
      </div>
    </header>

    <div class="flex-1 overflow-y-auto p-3 space-y-4">
      <TextLayerInspector v-if="isText" />

      <template v-else-if="isBrushLike">
        <div class="space-y-1">
          <div class="flex items-center justify-between text-xs text-towa-text-muted">
            <span>크기</span>
            <span class="font-mono text-towa-text">{{ brushSize }}px</span>
          </div>
          <input v-model.number="brushSize" type="range" min="1" max="200" step="1" class="w-full accent-towa-accent" />
        </div>
        <div class="space-y-1">
          <div class="flex items-center justify-between text-xs text-towa-text-muted">
            <span>불투명도</span>
            <span class="font-mono text-towa-text">{{ Math.round(brushOpacity * 100) }}%</span>
          </div>
          <input v-model.number="brushOpacity" type="range" min="0" max="1" step="0.01" class="w-full accent-towa-accent" />
        </div>
      </template>

      <!-- 옵션 없는 도구는 의도적으로 빈 영역 (레이아웃 안정성) -->
    </div>
  </aside>
</template>
