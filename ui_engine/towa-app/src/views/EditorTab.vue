<script setup lang="ts">
import { computed, watch, ref, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { usePageLoader } from '@/composables/usePageLoader'
import { useAutoSave } from '@/composables/useAutoSave'
import PageSidePanel from '@/components/editor/PageSidePanel.vue'
import TranslationPanel from '@/components/editor/TranslationPanel.vue'
import AiToolbar from '@/components/editor/AiToolbar.vue'
import { isTextLayer, mergeTextMeta } from '@/utils/text-layer'
import type { Layer, Text } from '@bitmappery/definitions/document'
import { LayerTypes } from '@bitmappery/definitions/layer-types'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'
// @ts-expect-error bitmappery JS module
import ToolTypes from '@bitmappery/definitions/tool-types'

defineOptions({ name: 'EditorTab' })

const store = useStore()
const route = useRoute()
const { switchPage } = usePageLoader()
useAutoSave()

const projectId = computed(() => route.params.id as string)
const pages = computed(() => store.getters['pages/forProject'](projectId.value))
const selectedPageId = computed(() => store.getters['editor/selectedPageId'])
const currentPage = computed(() =>
  selectedPageId.value ? store.getters['pages/byId'](projectId.value, selectedPageId.value) : null
)
const selectedLayerId = computed<string | null>(() => store.getters['editor/selectedLayerId'])
const pagePanelCollapsed = computed(() => store.getters['editor/pagePanelCollapsed'])
const switching = ref(false)

const textLayers = computed<Layer[]>(() => {
  const doc = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  return (doc?.layers ?? []).filter(isTextLayer)
})

const currentPageIndex = computed(() => {
  if (!currentPage.value) return 0
  return currentPage.value.index
})

watch(
  [pages, selectedPageId],
  ([pageList, pageId]) => {
    if (!pageId && pageList.length > 0) {
      store.commit('editor/SET_SELECTED_PAGE', pageList[0].id)
    }
  },
  { immediate: true },
)

watch(selectedPageId, async (newId, oldId) => {
  if (!newId || newId === oldId || switching.value) return
  switching.value = true
  try {
    await switchPage(oldId ?? null, newId)
  } finally {
    switching.value = false
  }
}, { immediate: true })

function selectPage(pageId: string) {
  store.commit('editor/SET_SELECTED_PAGE', pageId)
}

function selectLayer(layerId: string) {
  store.commit('editor/SELECT_LAYER', layerId)
  const idx = findLayerIndex(layerId)
  if (idx >= 0) {
    store.commit('bmp/setActiveLayerIndex', idx)
    const doc = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
    const layer = doc?.layers?.[idx]
    if (layer?.type === LayerTypes.LAYER_TEXT) {
      store.commit('bmp/setActiveTool', { tool: ToolTypes.TEXT })
    }
  }
}

function setPanelCollapsed(collapsed: boolean) {
  store.commit('editor/SET_PAGE_PANEL_COLLAPSED', collapsed)
}

function findLayerIndex(layerId: string): number {
  const doc = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  return (doc?.layers ?? []).findIndex((l) => l.id === layerId)
}

function updateTextLayer(layerId: string, textPatch: Partial<Text>) {
  const idx = findLayerIndex(layerId)
  if (idx < 0) return
  const doc = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  const layer = doc?.layers?.[idx]
  if (!layer) return
  const nextText: Text = { ...layer.text, ...textPatch }
  const nextMeta = mergeTextMeta(layer, { status: 'edited' })
  store.commit('bmp/updateLayer', { index: idx, opts: { text: nextText, meta: nextMeta } })
}

function addEmptyTextLayer() {
  const doc = store.getters['bmp/activeDocument'] as { width?: number; height?: number; layers?: Layer[] } | undefined
  if (!doc) return
  // bitmappery 텍스트 layer는 layer.width/height 크기 canvas에 텍스트를 렌더링하므로
  // document 전체 크기로 만들어야 글자가 잘리지 않음. (기존 layer-add-text-layer.ts 패턴)
  const layer = LayerFactory.create({
    type: LayerTypes.LAYER_TEXT,
    left: 0,
    top: 0,
    width: doc.width ?? 800,
    height: doc.height ?? 1200,
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
    },
  }) as Layer
  layer.meta = { blockId: layer.id, original: '', status: 'edited', boxMode: 'fixed' }
  store.commit('bmp/addLayer', layer)
  store.commit('editor/SELECT_LAYER', layer.id)
  const layers = doc.layers ?? []
  store.commit('bmp/setActiveLayerIndex', layers.length) // 방금 추가됨 → 마지막 index
  store.commit('bmp/setActiveTool', { tool: ToolTypes.TEXT })
}

function removeTextLayer(layerId: string) {
  const idx = findLayerIndex(layerId)
  if (idx < 0) return
  store.commit('bmp/removeLayer', idx)
  if (selectedLayerId.value === layerId) {
    store.commit('editor/SELECT_LAYER', null)
  }
}

function goToPrevPage() {
  const idx = pages.value.findIndex((p: { id: string }) => p.id === selectedPageId.value)
  if (idx > 0) selectPage(pages.value[idx - 1].id)
}

function goToNextPage() {
  const idx = pages.value.findIndex((p: { id: string }) => p.id === selectedPageId.value)
  if (idx >= 0 && idx < pages.value.length - 1) selectPage(pages.value[idx + 1].id)
}

function onKeydown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement).tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
  if (e.key === 'q' || e.key === 'Q' || e.key === 'ㅂ' || e.code === 'KeyQ') {
    e.preventDefault(); goToPrevPage()
  } else if (e.key === 'w' || e.key === 'W' || e.key === 'ㅈ' || e.code === 'KeyW') {
    e.preventDefault(); goToNextPage()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div>
    <Teleport to="#towa-top-toolbar" defer>
      <AiToolbar />
    </Teleport>

    <Teleport to="#towa-left-panel" defer>
      <PageSidePanel
        :pages="pages"
        :current-page-id="selectedPageId"
        :collapsed="pagePanelCollapsed"
        @select-page="selectPage"
        @update:collapsed="setPanelCollapsed"
      />
    </Teleport>

    <Teleport to="#towa-right-panel" defer>
      <TranslationPanel
        :layers="textLayers"
        :selected-layer-id="selectedLayerId"
        :current-page-index="currentPageIndex"
        :total-pages="pages.length"
        @select-layer="selectLayer"
        @update-text="updateTextLayer"
        @add-block="addEmptyTextLayer"
        @remove-block="removeTextLayer"
        @prev-page="goToPrevPage"
        @next-page="goToNextPage"
      />
    </Teleport>
  </div>
</template>
