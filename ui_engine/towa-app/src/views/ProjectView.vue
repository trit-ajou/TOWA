<script setup lang="ts">
import { computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { useStore } from 'vuex'
// @ts-expect-error bitmappery component (JS/Vue)
import BitMappery from '@bitmappery/bitmappery.vue'
import { setTowaMode } from '@bitmappery/config/towa-mode-presets'
import PageTransitionOverlay from '@/components/common/PageTransitionOverlay.vue'
import { usePageLoader, resetPageLoaderState } from '@/composables/usePageLoader'
import { useProjects } from '@/composables/useProjects'

const route = useRoute()
const router = useRouter()
const store = useStore()
const { isPageSwitching } = usePageLoader()
const selectedPageIdForOverlay = computed<string | null>(() => store.getters['editor/selectedPageId'] ?? null)

const projectId = computed(() => route.params.id as string)
const projectsApi = useProjects()

// Project not-found / soft-deleted detection (#39 §404 흡수). Once the project
// list has loaded and the requested id isn't there, redirect to /library so
// the user lands somewhere sensible.
watch(
  [() => projectsApi.isLoading.value, projectId, () => projectsApi.all.value.length],
  () => {
    if (projectsApi.isLoading.value) return
    if (!projectsApi.byId(projectId.value)) {
      router.replace('/library').catch(() => {})
    }
  },
  { immediate: true },
)
const activeTab = computed(() => route.name as string)
const showCanvas = computed(() => activeTab.value === 'editor' || activeTab.value === 'detail-editor')

watch(projectId, (id) => {
  store.commit('editor/SET_CURRENT_PROJECT', id)
  // Pages are fetched lazily by the consumer composable (usePages) when each
  // tab mounts. No imperative pre-load needed.
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

// bitmappery 문서 정리는 unmount *전*에 끝낸다. closeActiveDocument는
// state.documents를 splice하고 flushLayerRenderers를 부르며 resource-manager가
// blob URL을 dispose한다. 이 cascade가 ProjectView unmount 도중에 발사되면
// inner router-view가 자식(EditorTab/DetailEditorTab) DOM을 조작하려는 시점에
// reactive update를 받아 parentNode null / insertBefore NotFoundError가 발생한다.
// (KeepAlive 제거(#39 freeze fix)와 같은 패턴의 별도 트리거 — 사용자 보고)
//
// onBeforeRouteLeave는 *route를 떠나는 시점*에 호출되고 ProjectView/자식들은
// 아직 mount 상태라 cascade가 정상 처리된다. child route 전환(편집 ↔ 상세편집)
// 에서는 호출되지 않으므로 documents가 잘못 닫히지 않는다.
onBeforeRouteLeave(() => {
  const docs = store.state.bmp?.document?.documents
  if (docs) {
    while (store.getters['bmp/activeDocument']) {
      store.commit('bmp/closeActiveDocument')
    }
  }
  resetPageLoaderState()
})

// 안전망: 비-router 경로로 unmount되는 케이스(테스트 등)에 한해 idempotent
// cleanup. onBeforeRouteLeave가 정상 실행됐다면 docs는 이미 비어있어 no-op.
// resetPageLoaderState도 함께 호출해 currentLoadedPageId가 stale로 남지 않게 한다
// (PR #59 self-review #5).
onBeforeUnmount(() => {
  const docs = store.state.bmp?.document?.documents
  if (docs) {
    while (store.getters['bmp/activeDocument']) {
      store.commit('bmp/closeActiveDocument')
    }
  }
  resetPageLoaderState()
})
</script>

<template>
  <div class="h-[calc(100vh-48px)] flex">
    <!-- 좌측 최외곽: 페이지 사이드패널 (EditorTab/DetailEditorTab이 주입) -->
    <div id="towa-left-panel" class="shrink-0 h-full"></div>

    <!-- 캔버스 워크스페이스: 상단 통합 바 + (좌 toolbox + 캔버스 + 우 옵션) -->
    <div class="flex-1 min-w-0 h-full flex flex-col bg-towa-bg">
      <!-- 상단 통합 바: AI 도구 / 줌 등 (Editor/DetailEditor 진입 시 주입) -->
      <div id="towa-canvas-topbar" class="shrink-0"></div>

      <div class="flex-1 min-h-0 flex">
        <!-- 캔버스 본체 + floating overlay 컨테이너 -->
        <div id="towa-canvas-area" class="flex-1 min-w-0 h-full relative">
          <div v-show="showCanvas" class="bitmappery-layer">
            <BitMappery />
          </div>
          <!-- KeepAlive 제거: vuejs/core#8509 — KeepAlive wrapper 안의 Teleport(defer)는
               빠른 자식 컴포넌트 swap 시 DOM이 stale하게 남아 다음 mount에서 insertBefore
               NotFoundError를 일으킨다. 우리는 EditorTab/DetailEditorTab을 캐시하지 않고
               ProjectHomeTab만 캐시했지만, KeepAlive 자체가 자식 lifecycle을 통제하므로
               include 여부와 무관하게 wrapper만으로도 #8509 증상이 발생한다.
               ProjectHomeTab 캐시 효과는 TanStack Query 캐시가 즉시 hit하므로 거의 0. -->
          <router-view />
        </div>

        <!-- 캔버스 우측 옵션/번역 패널 -->
        <div id="towa-right-panel" class="shrink-0 h-full"></div>
      </div>
    </div>

    <!-- 페이지 전환 시 캔버스 깜빡임을 가리는 overlay. 짧은 전환에 거슬리지 않도록
         delay를 300ms로 설정 — NN/g UX 가이드: 100ms는 즉각 인지(불필요), 300ms부터
         사용자가 명확히 기다림을 인지. cache hit 단순 전환은 100ms 근처라 overlay 미노출. -->
    <PageTransitionOverlay :visible="isPageSwitching" :delay="300" :page-id="selectedPageIdForOverlay" />
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
