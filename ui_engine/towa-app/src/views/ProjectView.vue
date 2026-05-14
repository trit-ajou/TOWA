<script setup lang="ts">
import { computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { useStore } from 'vuex'
// @ts-expect-error bitmappery component (JS/Vue)
import BitMappery from '@bitmappery/bitmappery.vue'
import { setTowaMode } from '@bitmappery/config/towa-mode-presets'
import PageTransitionOverlay from '@/components/common/PageTransitionOverlay.vue'
import { usePageLoader } from '@/composables/usePageLoader'

const route = useRoute()
const store = useStore()
const { isPageSwitching } = usePageLoader()

const projectId = computed(() => route.params.id as string)
const activeTab = computed(() => route.name as string)
const showCanvas = computed(() => activeTab.value === 'editor' || activeTab.value === 'detail-editor')

watch(projectId, (id) => {
  store.commit('editor/SET_CURRENT_PROJECT', id)
  store.dispatch('pages/loadForProject', id)
}, { immediate: true })

watch(
  () => route.name,
  (name) => {
    if (name === 'project-home') store.commit('editor/SET_ACTIVE_TAB', 'home')
    else if (name === 'editor') {
      store.commit('editor/SET_ACTIVE_TAB', 'edit')
      store.commit('editor/SET_LAST_EDIT_MODE', 'edit')
      setTowaMode('translator')
    }
    else if (name === 'detail-editor') {
      store.commit('editor/SET_ACTIVE_TAB', 'detail')
      store.commit('editor/SET_LAST_EDIT_MODE', 'detail')
      setTowaMode('typesetter')
    }
  },
  { immediate: true },
)

// display:none → visible 전환 시 bitmappery 캔버스 크기 재계산
watch(showCanvas, (visible) => {
  if (visible) {
    nextTick(() => window.dispatchEvent(new Event('resize')))
  }
})

// ProjectView unmount 시 bitmappery 문서 정리
// (홈으로 돌아가면 ProjectView가 통째로 unmount되는데,
//  이때 canvas-service의 참조를 정리하지 않으면 다음 진입 시 캔버스가 재생성되지 않음)
onBeforeUnmount(() => {
  const docs = store.state.bmp?.document?.documents
  if (docs) {
    // 모든 열린 문서 닫기
    while (store.getters['bmp/activeDocument']) {
      store.commit('bmp/closeActiveDocument')
    }
  }
})
</script>

<template>
  <div class="h-[calc(100vh-48px)] flex">
    <!-- 좌측: Teleport target (EditorTab/DetailEditorTab이 PageSidePanel 주입) -->
    <div id="towa-left-panel" class="shrink-0 h-full"></div>

    <!-- 중앙: top toolbar + bitmappery + router-view -->
    <div class="flex-1 min-w-0 h-full relative flex flex-col">
      <!-- 상단 Teleport target (EditorTab/DetailEditorTab이 AiToolbar 주입) -->
      <div id="towa-top-toolbar" class="shrink-0"></div>
      <div class="flex-1 min-h-0 relative">
        <div v-show="showCanvas" class="bitmappery-layer">
          <BitMappery />
        </div>
        <router-view v-slot="{ Component }">
          <keep-alive :include="['ProjectHomeTab']">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </div>
    </div>

    <!-- 우측: Teleport target (EditorTab이 TranslationPanel 주입) -->
    <div id="towa-right-panel" class="shrink-0 h-full"></div>

    <!-- 페이지 전환 시 캔버스 깜빡임을 가리는 overlay (100ms 이상 전환에서만 노출) -->
    <PageTransitionOverlay :visible="isPageSwitching" :delay="100" />
  </div>
</template>

<style scoped>
.bitmappery-layer {
  position: absolute;
  inset: 0;
  overflow: hidden;
  isolation: isolate;

  --bmp-accent: var(--towa-accent);
  --bmp-secondary: var(--towa-surface);
  --bmp-warning: var(--towa-warning);
  --bmp-danger: var(--towa-danger);
  --bmp-bg: var(--towa-surface-light);
  --bmp-bg-dark: var(--towa-bg);
  --bmp-bg-light: var(--towa-surface);
  --bmp-text: var(--towa-text);
  --bmp-lines: var(--towa-border);
}
</style>
