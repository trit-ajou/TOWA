<script setup lang="ts">
import { computed, watch, ref, provide } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { usePageLoader } from '@/composables/usePageLoader'
import { useAutoSave } from '@/composables/useAutoSave'
import { useSpacePanModifier } from '@/composables/useSpacePanModifier'
import { usePages } from '@/composables/usePages'
import { usePageBinaryPrefetch } from '@/composables/usePageBinaryPrefetch'
import PageSidePanel from '@/components/editor/PageSidePanel.vue'
import CanvasToolbox from '@/components/editor/CanvasToolbox.vue'
import ToolOptionsPanel from '@/components/editor/ToolOptionsPanel.vue'
import LayerPanel from '@/components/editor/LayerPanel.vue'
import RightPanelSplit from '@/components/editor/RightPanelSplit.vue'
import ZoomToolHandler from '@/components/editor/ZoomToolHandler.vue'
import AiProgressOverlay from '@/components/editor/AiProgressOverlay.vue'
import BrushOptionsPopover from '@/components/editor/BrushOptionsPopover.vue'
import EyedropperHandler from '@/components/editor/EyedropperHandler.vue'
import CanvasNoticeToast from '@/components/editor/CanvasNoticeToast.vue'
import PaintGuard from '@/components/editor/PaintGuard.vue'
import ErrorDialogStack from '@/components/editor/ErrorDialogStack.vue'

defineOptions({ name: 'DetailEditorTab' })

useSpacePanModifier()

const store = useStore()
const route = useRoute()
const { switchPage } = usePageLoader()
const { saveImmediately, markDirty } = useAutoSave()
// bmp/addLayer·removeLayer·reorderLayers 등은 bitmappery history에 안 들어가서
// historyIndex watch가 못 잡는다. 자식 컴포넌트(LayerPanel 등)에서 수동으로
// dirty 플래그를 세팅할 수 있도록 inject로 노출.
provide('markDirty', markDirty)

const projectId = computed(() => route.params.id as string)
const pagesApi = usePages(projectId)
const pages = pagesApi.list
const selectedPageId = computed(() => store.getters['editor/selectedPageId'])

usePageBinaryPrefetch({
  pageIds: computed(() => pages.value.map((p) => p.id)),
  activePageId: selectedPageId,
})
const pagePanelCollapsed = computed(() => store.getters['editor/pagePanelCollapsed'])
const switching = ref(false)

// 첫 페이지 자동 선택
watch(
  [pages, selectedPageId],
  ([pageList, pageId]) => {
    if (!pageId && pageList.length > 0) {
      store.commit('editor/SET_SELECTED_PAGE', pageList[0].id)
    }
  },
  { immediate: true },
)

// 페이지 변경 시 bitmappery에 자동 로드 (초기 진입 포함)
watch(selectedPageId, async (newId, oldId) => {
  if (!newId || newId === oldId || switching.value) return
  switching.value = true
  try {
    if (oldId) await saveImmediately(oldId)
    await switchPage(oldId ?? null, newId)
  } finally {
    switching.value = false
  }
}, { immediate: true })

function selectPage(pageId: string) {
  store.commit('editor/SET_SELECTED_PAGE', pageId)
}

function setPanelCollapsed(collapsed: boolean) {
  store.commit('editor/SET_PAGE_PANEL_COLLAPSED', collapsed)
}
</script>

<template>
  <div>
    <Teleport to="#towa-left-panel" defer>
      <PageSidePanel
        :pages="pages"
        :current-page-id="selectedPageId"
        :collapsed="pagePanelCollapsed"
        @select-page="selectPage"
        @update:collapsed="setPanelCollapsed"
      />
    </Teleport>

    <Teleport to="#towa-canvas-area" defer>
      <ZoomToolHandler />
      <CanvasToolbox />
      <AiProgressOverlay />
      <BrushOptionsPopover />
      <EyedropperHandler />
      <PaintGuard />
      <CanvasNoticeToast />
      <ErrorDialogStack />
    </Teleport>

    <Teleport to="#towa-right-panel" defer>
      <RightPanelSplit>
        <template #top><ToolOptionsPanel /></template>
        <template #bottom><LayerPanel /></template>
      </RightPanelSplit>
    </Teleport>
  </div>
</template>
