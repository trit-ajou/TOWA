<script setup lang="ts">
import { computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useStore } from 'vuex'
// @ts-expect-error bitmappery component (JS/Vue)
import BitMappery from '@bitmappery/bitmappery.vue'
import { setTowaMode } from '@bitmappery/config/towa-mode-presets'

const route = useRoute()
const store = useStore()

const projectId = computed(() => route.params.id as string)
const activeTab = computed(() => route.name as string)
const showCanvas = computed(() => activeTab.value === 'editor' || activeTab.value === 'detail-editor')

watch(projectId, (id) => {
  store.commit('editor/SET_CURRENT_PROJECT', id)
  // IndexedDB에서 페이지 목록 로드
  store.dispatch('pages/loadForProject', id)
}, { immediate: true })

// Sync activeTab with route
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

// 문서가 없으면 빈 문서 자동 생성 (임시 — 추후 File Adapter가 페이지 이미지를 로드)
onMounted(() => {
  const activeDoc = store.getters['bmp/activeDocument']
  if (!activeDoc) {
    store.commit('bmp/addNewDocument', 'Untitled')
  }
})
</script>

<template>
  <div class="h-[calc(100vh-48px)] relative">
    <!-- bitmappery 캔버스: ③④에서 공유, ②에서는 백그라운드 초기화 (z-index: 0) -->
    <div
      class="bitmappery-layer"
      :class="{ 'bitmappery-layer--hidden': !showCanvas }"
    >
      <BitMappery />
    </div>

    <!-- 탭 UI: bitmappery 위에 표시 (z-index: 1) -->
    <div class="tab-layer" :class="{ 'tab-layer--passthrough': showCanvas }">
      <router-view v-slot="{ Component }">
        <keep-alive :include="['ProjectHomeTab', 'EditorTab', 'DetailEditorTab']">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </div>
  </div>
</template>

<style scoped>
.bitmappery-layer {
  position: absolute;
  inset: 0;
  pointer-events: auto;
  isolation: isolate;

  /* towa 테마 → bitmappery CSS 변수 매핑 */
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

.bitmappery-layer--hidden {
  display: none;
}

.tab-layer {
  position: absolute;
  inset: 0;
  z-index: 1;
}

/* 캔버스가 보일 때: 탭 UI는 pointer-events 투과 (사이드 패널만 pointer-events-auto) */
.tab-layer--passthrough {
  pointer-events: none;
}
</style>
