<script setup lang="ts">
import { computed, watch } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { Paintbrush } from 'lucide-vue-next'
import PageSidePanel from '@/components/editor/PageSidePanel.vue'

defineOptions({ name: 'DetailEditorTab' })

const store = useStore()
const route = useRoute()

const projectId = computed(() => route.params.id as string)
const pages = computed(() => store.getters['pages/forProject'](projectId.value))
const selectedPageId = computed(() => store.getters['editor/selectedPageId'])
const pagePanelCollapsed = computed(() => store.getters['editor/pagePanelCollapsed'])

watch(
  [pages, selectedPageId],
  ([pageList, pageId]) => {
    if (!pageId && pageList.length > 0) {
      store.commit('editor/SET_SELECTED_PAGE', pageList[0].id)
    }
  },
  { immediate: true },
)

function selectPage(pageId: string) {
  store.commit('editor/SET_SELECTED_PAGE', pageId)
}

function setPanelCollapsed(collapsed: boolean) {
  store.commit('editor/SET_PAGE_PANEL_COLLAPSED', collapsed)
}
</script>

<template>
  <div class="h-full flex">
    <PageSidePanel
      :pages="pages"
      :current-page-id="selectedPageId"
      :collapsed="pagePanelCollapsed"
      @select-page="selectPage"
      @update:collapsed="setPanelCollapsed"
    />

    <div class="flex-1 flex flex-col items-center justify-center gap-6 bg-towa-bg">
      <div class="text-center">
        <div class="w-16 h-16 rounded-full bg-towa-surface-light flex items-center justify-center mx-auto mb-4">
          <Paintbrush :size="32" class="text-towa-accent" />
        </div>
        <h2 class="text-xl font-semibold text-towa-text mb-2">상세 편집 (식자 모드)</h2>
        <p class="text-sm text-towa-text-muted max-w-md">
          bitmappery 기반 이미지 편집 도구가 통합될 예정입니다.<br />
          인페인팅 수정, 텍스트 위치 조정, 이미지 보정 등의 작업을 수행합니다.
        </p>
      </div>
    </div>
  </div>
</template>
