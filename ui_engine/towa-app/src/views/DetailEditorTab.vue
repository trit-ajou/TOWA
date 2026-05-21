<script setup lang="ts">
import { computed, watch, ref } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { usePageLoader } from '@/composables/usePageLoader'
import { useAutoSave } from '@/composables/useAutoSave'
import PageSidePanel from '@/components/editor/PageSidePanel.vue'
import AiToolbar from '@/components/editor/AiToolbar.vue'

defineOptions({ name: 'DetailEditorTab' })

const store = useStore()
const route = useRoute()
const { switchPage } = usePageLoader()
const { saveImmediately } = useAutoSave()

const projectId = computed(() => route.params.id as string)
const pages = computed(() => store.getters['pages/forProject'](projectId.value))
const selectedPageId = computed(() => store.getters['editor/selectedPageId'])
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
  </div>
</template>
