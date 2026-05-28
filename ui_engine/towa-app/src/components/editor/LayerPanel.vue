<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStore } from 'vuex'
import { Eye, EyeOff, Type, Image as ImageIcon, Trash2, Plus, ChevronDown, ChevronRight } from 'lucide-vue-next'
import type { Layer } from '@bitmappery/definitions/document'
import { LayerTypes } from '@bitmappery/definitions/layer-types'
import { classifyLayer, type LayerGroupId } from '@/utils/layer-classify'

const store = useStore()

const layers = computed<Layer[]>(() => store.getters['bmp/activeDocument']?.layers ?? [])
const activeLayerIndex = computed<number>(() => store.getters['bmp/activeLayerIndex'] ?? 0)
const activeDocument = computed(() => store.getters['bmp/activeDocument'])

interface LayerEntry { layer: Layer; index: number }
interface LayerGroup {
  id: LayerGroupId
  label: string
  layers: LayerEntry[]
}

// 포토샵 관습: 위가 최상위 z-order. 그룹 안에서도 layers 배열의 끝(상위)이 먼저 보이도록 reverse
const groups = computed<LayerGroup[]>(() => {
  const buckets: Record<LayerGroup['id'], LayerEntry[]> = {
    custom: [], text: [], inpaint: [], original: [],
  }
  layers.value.forEach((layer, index) => {
    buckets[classifyLayer(layer)].push({ layer, index })
  })
  // 그룹 표시 순서: 위가 z-order 상단 (사용자 의도: 커스텀이 텍스트 위, 인페인트 아래, 원본 맨 아래)
  return [
    { id: 'custom',   label: '커스텀',   layers: buckets.custom.reverse() },
    { id: 'text',     label: '텍스트',   layers: buckets.text.reverse() },
    { id: 'inpaint',  label: '인페인트', layers: buckets.inpaint.reverse() },
    { id: 'original', label: '원본',     layers: buckets.original.reverse() },
  ]
})

const collapsed = ref<Record<LayerGroup['id'], boolean>>({
  custom: false, text: false, inpaint: false, original: false,
})
function toggleGroup(id: LayerGroup['id']) { collapsed.value[id] = !collapsed.value[id] }

function selectLayer(index: number) {
  store.commit('bmp/setActiveLayerIndex', index)
}
function toggleVisibility(layer: Layer, index: number) {
  store.commit('bmp/updateLayer', { index, opts: { visible: !layer.visible } })
}
function removeLayer(index: number) {
  store.commit('bmp/removeLayer', index)
}
function addLayer() {
  if (!activeDocument.value) return
  store.commit('bmp/addLayer', {
    name: 'New Layer',
    type: LayerTypes.LAYER_GRAPHIC,
    visible: true,
    width: activeDocument.value.width ?? 800,
    height: activeDocument.value.height ?? 1200,
    left: 0, top: 0,
  })
}

function layerIcon(type: string) {
  if (type === LayerTypes.LAYER_TEXT) return Type
  return ImageIcon
}
function layerLabel(layer: Layer, index: number): string {
  if (layer.type === LayerTypes.LAYER_TEXT) {
    const value = layer.text?.value?.trim()
    if (value) return value
    return '(빈 텍스트)'
  }
  return layer.name || `Layer ${index + 1}`
}
</script>

<template>
  <section class="flex flex-col h-full bg-towa-surface border-t border-towa-border">
    <header class="flex items-center justify-between px-3 py-2 border-b border-towa-border shrink-0">
      <div>
        <div class="text-xs uppercase tracking-wider text-towa-text-muted">레이어</div>
        <div class="text-sm font-medium text-towa-text mt-0.5">{{ layers.length }}개</div>
      </div>
      <button
        class="p-1 rounded text-towa-text-muted hover:text-towa-accent hover:bg-towa-surface-light transition-colors"
        title="새 레이어"
        :disabled="!activeDocument"
        @click="addLayer"
      >
        <Plus :size="16" />
      </button>
    </header>

    <div v-if="layers.length > 0" class="flex-1 overflow-y-auto py-1">
      <div v-for="group in groups" :key="group.id" class="mb-1">
        <!-- 그룹 헤더 -->
        <button
          class="w-full flex items-center gap-1 px-2 py-1 text-[11px] uppercase tracking-wider text-towa-text-muted hover:text-towa-text transition-colors"
          :title="collapsed[group.id] ? '펼치기' : '접기'"
          @click="toggleGroup(group.id)"
        >
          <ChevronDown v-if="!collapsed[group.id]" :size="12" />
          <ChevronRight v-else :size="12" />
          <span class="font-semibold">{{ group.label }}</span>
          <span class="ml-1 text-towa-text-muted/70 normal-case tracking-normal">{{ group.layers.length }}</span>
        </button>

        <!-- 그룹 안 레이어 -->
        <ul v-if="!collapsed[group.id] && group.layers.length > 0">
          <li
            v-for="entry in group.layers"
            :key="entry.layer.id"
            class="group flex items-center gap-2 pl-4 pr-2 py-1.5 mx-1 rounded cursor-pointer transition-colors"
            :class="entry.index === activeLayerIndex
              ? 'bg-towa-accent/20 border-l-2 border-towa-accent'
              : 'hover:bg-towa-surface-light border-l-2 border-transparent'"
            @click="selectLayer(entry.index)"
          >
            <button
              class="shrink-0 text-towa-text-muted hover:text-towa-text"
              :title="entry.layer.visible ? '숨기기' : '표시'"
              @click.stop="toggleVisibility(entry.layer, entry.index)"
            >
              <Eye v-if="entry.layer.visible" :size="14" />
              <EyeOff v-else :size="14" />
            </button>
            <component :is="layerIcon(entry.layer.type)" :size="14" class="shrink-0 text-towa-text-muted" />
            <span
              class="flex-1 text-xs truncate"
              :class="entry.index === activeLayerIndex ? 'text-towa-text font-medium' : 'text-towa-text-muted'"
              :title="layerLabel(entry.layer, entry.index)"
            >
              {{ layerLabel(entry.layer, entry.index) }}
            </span>
            <button
              class="shrink-0 opacity-0 group-hover:opacity-100 text-towa-text-muted hover:text-towa-danger transition-opacity"
              title="삭제"
              @click.stop="removeLayer(entry.index)"
            >
              <Trash2 :size="13" />
            </button>
          </li>
        </ul>

        <!-- 빈 그룹: 펼친 상태일 때만 안내 -->
        <div
          v-else-if="!collapsed[group.id]"
          class="px-4 py-1 text-[11px] text-towa-text-muted/60 italic"
        >
          비어 있음
        </div>
      </div>
    </div>

    <div v-else class="flex-1 flex items-center justify-center text-xs text-towa-text-muted">
      레이어가 없습니다
    </div>
  </section>
</template>
