<script setup lang="ts">
import { computed, watch, ref, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { usePageLoader } from '@/composables/usePageLoader'
import { useAutoSave } from '@/composables/useAutoSave'
import { useSpacePanModifier } from '@/composables/useSpacePanModifier'
import PageSidePanel from '@/components/editor/PageSidePanel.vue'
import TranslationPanel from '@/components/editor/TranslationPanel.vue'
import CanvasToolbox from '@/components/editor/CanvasToolbox.vue'
import ZoomToolHandler from '@/components/editor/ZoomToolHandler.vue'
import TextBoxOverlay from '@/components/editor/TextBoxOverlay.vue'
import TextBoxCreator from '@/components/editor/TextBoxCreator.vue'
import AiProgressOverlay from '@/components/editor/AiProgressOverlay.vue'
import BrushOptionsPopover from '@/components/editor/BrushOptionsPopover.vue'
import EyedropperHandler from '@/components/editor/EyedropperHandler.vue'
import CanvasNoticeToast from '@/components/editor/CanvasNoticeToast.vue'
import PaintGuard from '@/components/editor/PaintGuard.vue'
import ErrorDialogStack from '@/components/editor/ErrorDialogStack.vue'
import { isTextLayer, mergeTextMeta } from '@/utils/text-layer'
import type { Layer, Text } from '@bitmappery/definitions/document'
import { LayerTypes } from '@bitmappery/definitions/layer-types'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'
// @ts-expect-error bitmappery JS module
import ToolTypes from '@bitmappery/definitions/tool-types'

defineOptions({ name: 'EditorTab' })

useSpacePanModifier()

const store = useStore()
const route = useRoute()
const { switchPage } = usePageLoader()
const { saveImmediately, markDirty } = useAutoSave()

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

// Deselect text layer when leaving the text tool. The bitmappery active-layer
// outline (mint border) would otherwise persist on the text layer's full-doc
// canvas, which is visually noisy in 편집 화면. 상세 편집 화면(DetailEditorTab)
// is unaffected — this watcher lives in EditorTab only.
const activeTool = computed<string | null>(() => store.getters['bmp/activeTool'] ?? null)
watch(activeTool, (next, prev) => {
  if (prev === ToolTypes.TEXT && next !== ToolTypes.TEXT) {
    const layer = store.getters['bmp/activeLayer'] as Layer | undefined
    if (layer && isTextLayer(layer)) {
      store.commit('bmp/setActiveLayerIndex', -1)
      store.commit('editor/SELECT_LAYER', null)
    }
  }
})

watch(selectedPageId, async (newId, oldId) => {
  if (!newId || newId === oldId || switching.value) return
  switching.value = true
  try {
    // dirty인 페이지만 즉시 서버 저장 (useAutoSave 내부에서 dirty 체크).
    // 변경 없으면 saveImmediately는 즉시 resolve → 도커 통신 없음.
    // saveImmediately는 명시적으로 떠나는 페이지 ID를 받아야 함.
    // selectedPageId는 이미 newId로 변경된 상태라 getter는 잘못된 페이지를 반환.
    if (oldId) await saveImmediately(oldId)
    await switchPage(oldId ?? null, newId)
  } finally {
    switching.value = false
  }
}, { immediate: true })

function selectPage(pageId: string) {
  store.commit('editor/SET_SELECTED_PAGE', pageId)
}

function selectLayer(layerId: string) {
  // Toggle: clicking the already-selected block deselects it.
  if (selectedLayerId.value === layerId) {
    store.commit('editor/SELECT_LAYER', null)
    store.commit('bmp/setActiveLayerIndex', -1)
    return
  }
  store.commit('editor/SELECT_LAYER', layerId)
  const idx = findLayerIndex(layerId)
  if (idx >= 0) {
    store.commit('bmp/setActiveLayerIndex', idx)
    const doc = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
    const layer = doc?.layers?.[idx]
    if (layer?.type === LayerTypes.LAYER_TEXT) {
      store.commit('bmp/setActiveTool', { tool: ToolTypes.TEXT, document: doc })
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
  markDirty()
}

function updateOriginalForLayer(layerId: string, nextOriginal: string) {
  const idx = findLayerIndex(layerId)
  if (idx < 0) return
  const doc = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  const layer = doc?.layers?.[idx]
  if (!layer) return
  const nextMeta = mergeTextMeta(layer, { original: nextOriginal, status: 'edited' })
  store.commit('bmp/updateLayer', { index: idx, opts: { meta: nextMeta } })
  markDirty()
}

function addEmptyTextLayer() {
  const doc = store.getters['bmp/activeDocument'] as { width?: number; height?: number; layers?: Layer[] } | undefined
  if (!doc) return
  // Center a small box; user can drag-resize via overlay handles. Width is
  // 25% of the doc width (clamped) so it scales reasonably across panel sizes.
  const docW = doc.width ?? 800
  const docH = doc.height ?? 1200
  const width = Math.max(120, Math.min(300, Math.round(docW * 0.25)))
  const height = Math.max(60, Math.round(width * 0.4))
  const left = Math.round((docW - width) / 2)
  const top = Math.round((docH - height) / 2)
  const layer = LayerFactory.create({
    type: LayerTypes.LAYER_TEXT,
    left,
    top,
    width,
    height,
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
  // bmp/addLayer가 mutation 안에서 state.activeLayerIndex를 자동으로 새 layer의
  // 인덱스로 설정함 (document-module.ts addLayer). 여기서 또 commit하면 layers.length가
  // 이미 +1 된 시점 값이라 out-of-bounds (N+1)로 덮어쓰는 회귀가 됨.
  store.commit('bmp/addLayer', layer)
  store.commit('editor/SELECT_LAYER', layer.id)
  store.commit('bmp/setActiveTool', { tool: ToolTypes.TEXT, document: doc })
  markDirty()
}

function removeTextLayer(layerId: string) {
  const idx = findLayerIndex(layerId)
  if (idx < 0) return
  store.commit('bmp/removeLayer', idx)
  markDirty()
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
  if (e.ctrlKey || e.metaKey || e.altKey) return
  if (e.code === 'ArrowLeft') {
    e.preventDefault(); goToPrevPage()
  } else if (e.code === 'ArrowRight') {
    e.preventDefault(); goToNextPage()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div>
    <Teleport to="#towa-canvas-area" defer>
      <ZoomToolHandler />
      <CanvasToolbox />
      <AiProgressOverlay />
      <BrushOptionsPopover />
      <EyedropperHandler />
      <PaintGuard />
      <CanvasNoticeToast />
      <ErrorDialogStack />
      <TextBoxCreator />
      <TextBoxOverlay />
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
        @update-original="updateOriginalForLayer"
        @add-block="addEmptyTextLayer"
        @remove-block="removeTextLayer"
        @prev-page="goToPrevPage"
        @next-page="goToNextPage"
      />
    </Teleport>
  </div>
</template>
