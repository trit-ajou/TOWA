<script setup lang="ts">
import { ref, computed } from 'vue'
import { useStore } from 'vuex'
import { ScanText, Eraser, Languages, ZoomIn, ZoomOut, Columns2, Square } from 'lucide-vue-next'
import BaseButton from '@/components/common/BaseButton.vue'

const store = useStore()
const loading = ref<string | null>(null)

const zoomLevel = computed(() => store.getters['editor/zoomLevel'])
const viewMode = computed(() => store.getters['editor/canvasViewMode'])

async function runAction(action: string) {
  loading.value = action
  await new Promise((resolve) => setTimeout(resolve, 1500))
  loading.value = null
}

function zoomIn() {
  store.commit('editor/SET_ZOOM', zoomLevel.value + 25)
}
function zoomOut() {
  store.commit('editor/SET_ZOOM', zoomLevel.value - 25)
}
function setViewMode(mode: 'single-split' | 'spread') {
  store.commit('editor/SET_CANVAS_VIEW_MODE', mode)
}

const actions = [
  { id: 'detect', label: '텍스트 검출', icon: ScanText },
  { id: 'inpaint', label: '인페인팅', icon: Eraser },
  { id: 'translate', label: '번역', icon: Languages },
]
</script>

<template>
  <div class="flex items-center justify-between px-3 py-1.5 bg-towa-surface border-b border-towa-border shrink-0">
    <!-- Left: AI tools -->
    <div class="flex items-center gap-1.5">
      <BaseButton
        v-for="action in actions"
        :key="action.id"
        variant="ghost"
        size="sm"
        :disabled="loading !== null"
        @click="runAction(action.id)"
      >
        <component :is="action.icon" :size="14" :class="{ 'animate-pulse': loading === action.id }" />
        {{ action.label }}
        <span v-if="loading === action.id" class="ml-1 text-[10px] text-towa-accent">처리중...</span>
      </BaseButton>
    </div>

    <!-- Right: view mode + zoom -->
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-1 bg-towa-bg rounded-md p-0.5">
        <button
          class="p-1 rounded transition-colors"
          :class="viewMode === 'single-split' ? 'bg-towa-surface-light text-towa-text' : 'text-towa-text-muted hover:text-towa-text'"
          title="한쪽보기"
          @click="setViewMode('single-split')"
        >
          <Columns2 :size="14" />
        </button>
        <button
          class="p-1 rounded transition-colors"
          :class="viewMode === 'spread' ? 'bg-towa-surface-light text-towa-text' : 'text-towa-text-muted hover:text-towa-text'"
          title="두쪽보기"
          @click="setViewMode('spread')"
        >
          <Square :size="14" />
        </button>
      </div>

      <div class="flex items-center gap-1">
        <button class="p-1 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-text transition-colors" @click="zoomOut">
          <ZoomOut :size="14" />
        </button>
        <span class="text-xs text-towa-text-muted w-10 text-center">{{ zoomLevel }}%</span>
        <button class="p-1 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-text transition-colors" @click="zoomIn">
          <ZoomIn :size="14" />
        </button>
      </div>
    </div>
  </div>
</template>
