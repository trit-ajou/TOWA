<script setup lang="ts">
import { computed, watch, ref } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { usePageLoader } from '@/composables/usePageLoader'
import { useAutoSave } from '@/composables/useAutoSave'
import PageSidePanel from '@/components/editor/PageSidePanel.vue'

defineOptions({ name: 'DetailEditorTab' })

const store = useStore()
const route = useRoute()
const { switchPage } = usePageLoader()
useAutoSave()

const projectId = computed(() => route.params.id as string)
const pages = computed(() => store.getters['pages/forProject'](projectId.value))
const selectedPageId = computed(() => store.getters['editor/selectedPageId'])
const pagePanelCollapsed = computed(() => store.getters['editor/pagePanelCollapsed'])
const switching = ref(false)

watch(
  [pages, selectedPageId],
  ([pageList, pageId]) => {
    if (!pageId && pageList.length > 0) {
      store.commit('editor/SET_SELECTED_PAGE', pageList[0].id)
    }
  },
  { immediate: true },
)

async function selectPage(pageId: string) {
  if (switching.value || pageId === selectedPageId.value) return
  switching.value = true
  try {
    await switchPage(selectedPageId.value, pageId)
    store.commit('editor/SET_SELECTED_PAGE', pageId)
  } finally {
    switching.value = false
  }
}

function setPanelCollapsed(collapsed: boolean) {
  store.commit('editor/SET_PAGE_PANEL_COLLAPSED', collapsed)
}
</script>

<template>
  <div class="h-full flex pointer-events-none">
    <!-- 좌측: 페이지 사이드 패널 -->
    <div class="pointer-events-auto">
      <PageSidePanel
        :pages="pages"
        :current-page-id="selectedPageId"
        :collapsed="pagePanelCollapsed"
        @select-page="selectPage"
        @update:collapsed="setPanelCollapsed"
      />
    </div>

    <!-- 중앙+우측: 투명 — bitmappery가 ProjectView에서 뒤에 렌더링됨 (typesetter 전체 도구) -->
    <div class="flex-1" />
  </div>
</template>
