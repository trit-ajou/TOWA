<script setup lang="ts">
import { computed } from 'vue'
import { useStore } from 'vuex'
import TextLayerInspector from './TextLayerInspector.vue'

const store = useStore()
const activeTool = computed<string | null>(() => store.getters['bmp/activeTool'])
const activeToolOptions = computed<Record<string, unknown> | undefined>(() => store.getters['bmp/activeToolOptions'])
const isText = computed(() => activeTool.value === 'text')

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
</script>

<template>
  <aside class="w-full h-full bg-towa-surface border-l border-towa-border flex flex-col">
    <header class="px-3 py-2 border-b border-towa-border">
      <div class="text-xs uppercase tracking-wider text-towa-text-muted">도구 옵션</div>
      <div class="text-sm font-medium text-towa-text mt-0.5">{{ label }}</div>
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
