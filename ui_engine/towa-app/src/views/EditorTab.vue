<script setup lang="ts">
import { computed, watch, ref, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import { usePageLoader } from '@/composables/usePageLoader'
import { useAutoSave } from '@/composables/useAutoSave'
import PageSidePanel from '@/components/editor/PageSidePanel.vue'
import TranslationPanel from '@/components/editor/TranslationPanel.vue'

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
const selectedBlockId = computed(() => store.getters['editor/selectedTextBlockId'])
const pagePanelCollapsed = computed(() => store.getters['editor/pagePanelCollapsed'])
const switching = ref(false)

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

function selectBlock(blockId: string) {
  store.commit('editor/SELECT_TEXT_BLOCK', blockId)
}

function setPanelCollapsed(collapsed: boolean) {
  store.commit('editor/SET_PAGE_PANEL_COLLAPSED', collapsed)
}

function goToPrevPage() {
  const idx = pages.value.findIndex((p: { id: string }) => p.id === selectedPageId.value)
  if (idx > 0) {
    selectPage(pages.value[idx - 1].id)
  }
}

function goToNextPage() {
  const idx = pages.value.findIndex((p: { id: string }) => p.id === selectedPageId.value)
  if (idx >= 0 && idx < pages.value.length - 1) {
    selectPage(pages.value[idx + 1].id)
  }
}

function onKeydown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement).tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

  if (e.key === 'q' || e.key === 'Q' || e.key === 'ㅂ' || e.code === 'KeyQ') {
    e.preventDefault()
    goToPrevPage()
  } else if (e.key === 'w' || e.key === 'W' || e.key === 'ㅈ' || e.code === 'KeyW') {
    e.preventDefault()
    goToNextPage()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
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

    <!-- 중앙: 투명 — bitmappery가 ProjectView에서 뒤에 렌더링됨 -->
    <div class="flex-1" />

    <!-- 우측: 번역 패널 -->
    <div class="pointer-events-auto">
      <TranslationPanel
        :blocks="currentPage?.textBlocks ?? []"
        :selected-block-id="selectedBlockId"
        :current-page-index="currentPageIndex"
        :total-pages="pages.length"
        @select-block="selectBlock"
        @prev-page="goToPrevPage"
        @next-page="goToNextPage"
      />
    </div>
  </div>
</template>
