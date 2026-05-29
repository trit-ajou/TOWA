<script setup lang="ts">
import { computed, ref, watch, inject } from 'vue'
import { useStore } from 'vuex'
import draggable from 'vuedraggable'
import { Eye, EyeOff, Type, Image as ImageIcon, Trash2, Plus, ChevronDown, ChevronRight, GripVertical } from 'lucide-vue-next'
import type { Layer } from '@bitmappery/definitions/document'
import { LayerTypes } from '@bitmappery/definitions/layer-types'
import { classifyLayer, type LayerGroupId } from '@/utils/layer-classify'

const store = useStore()
// 부모(DetailEditorTab)에서 provide. reorder/add/remove 같이 bitmappery history에
// 기록되지 않는 변경 후 호출해서 autoSave dirty 플래그를 세팅한다.
const markDirty = inject<() => void>('markDirty', () => {})

const layers = computed<Layer[]>(() => store.getters['bmp/activeDocument']?.layers ?? [])
const activeLayerIndex = computed<number>(() => store.getters['bmp/activeLayerIndex'] ?? 0)
const activeDocument = computed(() => store.getters['bmp/activeDocument'])

interface LayerEntry { layer: Layer; index: number }

// 그룹 표시 순서(위 = z-order 상단): 텍스트 → 커스텀 → 인페인트 → 원본
// 텍스트 레이어가 항상 최상단이라는 사용자 의도 (issue #50)
const groupsMeta: { id: LayerGroupId; label: string }[] = [
  { id: 'text', label: '텍스트' },
  { id: 'custom', label: '커스텀' },
  { id: 'inpaint', label: '인페인트' },
  { id: 'original', label: '원본' },
]

// 드래그 가능 그룹은 별도 ref로 관리해서 vuedraggable이 mutate할 수 있게 함.
// (computed로 만들면 readonly라 vuedraggable에서 못 씀)
const customList = ref<LayerEntry[]>([])
const inpaintList = ref<LayerEntry[]>([])
const textList = computed<LayerEntry[]>(() => bucketize().text.reverse())
const originalList = computed<LayerEntry[]>(() => bucketize().original.reverse())

function bucketize(): Record<LayerGroupId, LayerEntry[]> {
  const buckets: Record<LayerGroupId, LayerEntry[]> = {
    custom: [], text: [], inpaint: [], original: [],
  }
  layers.value.forEach((layer, index) => {
    buckets[classifyLayer(layer)].push({ layer, index })
  })
  return buckets
}

// store layers가 바뀌면 draggable용 ref 배열을 동기화.
// 단, 사용자가 드래그해서 reorderLayers를 막 부른 직후에도 watch가 다시 트리거되는데
// 이때 같은 순서가 반영되므로 무한 루프는 안 생긴다.
// deep: true 필요 — bmp/removeLayer는 splice(in-place)라 배열 reference가 안 바뀌고,
// bmp/updateLayer는 element를 새 object로 갈아끼우므로 표면 reference만 보면 LayerEntry가
// stale 상태로 남는다 (이전엔 페이지 전환해야 갱신됐던 원인).
watch(
  layers,
  () => {
    const buckets = bucketize()
    customList.value = buckets.custom.reverse()
    inpaintList.value = buckets.inpaint.reverse()
  },
  { immediate: true, deep: true },
)

const collapsed = ref<Record<LayerGroupId, boolean>>({
  custom: false, text: false, inpaint: false, original: false,
})
function toggleGroup(id: LayerGroupId) { collapsed.value[id] = !collapsed.value[id] }

function selectLayer(index: number) {
  store.commit('bmp/setActiveLayerIndex', index)
}
function toggleVisibility(layer: Layer, index: number) {
  store.commit('bmp/updateLayer', { index, opts: { visible: !layer.visible } })
  markDirty()
}
function removeLayer(index: number) {
  store.commit('bmp/removeLayer', index)
  markDirty()
}
function addLayer() {
  if (!activeDocument.value) return
  // 새 커스텀 graphic은 텍스트 직전에 insert해서 텍스트가 항상 위로 가도록 유지
  const buckets = bucketize()
  const firstTextEntry = buckets.text[0]
  const insertIndex = firstTextEntry ? firstTextEntry.index : layers.value.length
  store.commit('bmp/insertLayerAtIndex', {
    index: insertIndex,
    layer: {
      name: 'New Layer',
      type: LayerTypes.LAYER_GRAPHIC,
      visible: true,
      width: activeDocument.value.width ?? 800,
      height: activeDocument.value.height ?? 1200,
      left: 0, top: 0,
    },
  })
  markDirty()
}

function entryForGroup(id: LayerGroupId): LayerEntry[] {
  if (id === 'text') return textList.value
  if (id === 'original') return originalList.value
  if (id === 'custom') return customList.value
  return inpaintList.value
}

// 드래그&드롭 후 호출. UI 표시(위→아래)는 [text, custom, inpaint, original],
// 각 그룹 내부도 reverse되어 있으니, layers 배열(z-order 아래→위)로 재구성하려면
// [original, inpaint, custom, text]를 각각 다시 reverse해서 펼침.
function commitReorder() {
  const doc = activeDocument.value
  if (!doc) return

  // 1) 드롭된 위치에 따라 meta.role을 그 그룹에 맞게 갱신.
  //    그렇지 않으면 watch가 다음에 layers를 bucketize할 때 옛 role 기준으로 다시 분류돼
  //    그룹 간 이동이 즉시 원래대로 되돌아간다.
  for (const entry of inpaintList.value) {
    const current = (entry.layer.meta as { role?: string } | undefined)?.role
    if (current !== 'inpaint') {
      store.commit('bmp/updateLayer', {
        index: entry.index,
        opts: { meta: { ...(entry.layer.meta ?? {}), role: 'inpaint' } },
      })
    }
  }
  for (const entry of customList.value) {
    const current = (entry.layer.meta as { role?: string } | undefined)?.role
    if (current === 'inpaint') {
      const { role: _drop, ...rest } = (entry.layer.meta ?? {}) as Record<string, unknown>
      store.commit('bmp/updateLayer', {
        index: entry.index,
        opts: { meta: rest },
      })
    }
  }

  // 2) z-order 자체도 반영.
  const newOrder = [
    ...[...originalList.value].reverse(),
    ...[...inpaintList.value].reverse(),
    ...[...customList.value].reverse(),
    ...[...textList.value].reverse(),
  ].map((e) => e.layer.id as string)
  const originalOrder = layers.value.map((l) => (l as Layer).id as string)
  const orderChanged = !(originalOrder.length === newOrder.length && originalOrder.every((id, i) => id === newOrder[i]))
  if (orderChanged) {
    store.commit('bmp/reorderLayers', { document: doc, layerIds: newOrder })
  }
  markDirty()
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
      <div v-for="meta in groupsMeta" :key="meta.id" class="mb-1">
        <!-- 그룹 헤더 -->
        <button
          class="w-full flex items-center gap-1 px-2 py-1 text-[11px] uppercase tracking-wider text-towa-text-muted hover:text-towa-text transition-colors"
          :title="collapsed[meta.id] ? '펼치기' : '접기'"
          @click="toggleGroup(meta.id)"
        >
          <ChevronDown v-if="!collapsed[meta.id]" :size="12" />
          <ChevronRight v-else :size="12" />
          <span class="font-semibold">{{ meta.label }}</span>
          <span class="ml-1 text-towa-text-muted/70 normal-case tracking-normal">{{ entryForGroup(meta.id).length }}</span>
        </button>

        <!-- 드래그 가능 그룹 (커스텀 / 인페인트) -->
        <template v-if="!collapsed[meta.id] && (meta.id === 'custom' || meta.id === 'inpaint')">
          <draggable
            v-if="meta.id === 'custom'"
            v-model="customList"
            :group="{ name: 'movable-layers' }"
            item-key="layer.id"
            handle=".layer-drag-handle"
            tag="ul"
            ghost-class="opacity-40"
            @end="commitReorder"
          >
            <template #item="{ element: entry }">
              <li
                class="group flex items-center gap-2 pl-2 pr-2 py-1.5 mx-1 rounded cursor-pointer transition-colors"
                :class="entry.index === activeLayerIndex
                  ? 'bg-towa-accent/20 border-l-2 border-towa-accent'
                  : 'hover:bg-towa-surface-light border-l-2 border-transparent'"
                @click="selectLayer(entry.index)"
              >
                <span class="layer-drag-handle shrink-0 text-towa-text-muted/60 hover:text-towa-text cursor-grab active:cursor-grabbing" title="드래그하여 이동">
                  <GripVertical :size="12" />
                </span>
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
            </template>
          </draggable>
          <draggable
            v-else
            v-model="inpaintList"
            :group="{ name: 'movable-layers' }"
            item-key="layer.id"
            handle=".layer-drag-handle"
            tag="ul"
            ghost-class="opacity-40"
            @end="commitReorder"
          >
            <template #item="{ element: entry }">
              <li
                class="group flex items-center gap-2 pl-2 pr-2 py-1.5 mx-1 rounded cursor-pointer transition-colors"
                :class="entry.index === activeLayerIndex
                  ? 'bg-towa-accent/20 border-l-2 border-towa-accent'
                  : 'hover:bg-towa-surface-light border-l-2 border-transparent'"
                @click="selectLayer(entry.index)"
              >
                <span class="layer-drag-handle shrink-0 text-towa-text-muted/60 hover:text-towa-text cursor-grab active:cursor-grabbing" title="드래그하여 이동">
                  <GripVertical :size="12" />
                </span>
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
            </template>
          </draggable>
        </template>

        <!-- 고정 그룹 (텍스트 / 원본) -->
        <ul v-else-if="!collapsed[meta.id] && entryForGroup(meta.id).length > 0">
          <li
            v-for="entry in entryForGroup(meta.id)"
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
          v-if="!collapsed[meta.id] && entryForGroup(meta.id).length === 0"
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
