<script setup lang="ts">
import { ref, computed } from 'vue'
import { useStore } from 'vuex'
import { ScanText, Eraser, Languages, ZoomIn, ZoomOut, Columns2, Square } from 'lucide-vue-next'
import type { Page } from '@/types/page'

const props = defineProps<{
  currentPage: Page | null
  pages: Page[]
}>()

const store = useStore()
const zoomLevel = computed(() => store.getters['editor/zoomLevel'])
const viewMode = computed(() => store.getters['editor/canvasViewMode'])

const loading = ref<string | null>(null)

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

const adjacentPage = computed(() => {
  if (!props.currentPage) return null
  const idx = props.pages.findIndex((p) => p.id === props.currentPage!.id)
  if (idx < 0) return null
  return props.pages[idx + 1] ?? null
})

const aiActions = [
  { id: 'detect', label: '텍스트 검출', icon: ScanText },
  { id: 'inpaint', label: '인페인팅', icon: Eraser },
  { id: 'translate', label: '번역', icon: Languages },
]
</script>

<template>
  <div class="flex-1 flex flex-col min-w-0">
    <!-- Toolbar: integrated into canvas area -->
    <div class="flex items-center justify-between px-3 py-1 bg-towa-bg border-b border-towa-border shrink-0">
      <!-- Left: AI tools -->
      <div class="flex items-center gap-1">
        <button
          v-for="action in aiActions"
          :key="action.id"
          class="flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors"
          :class="loading === action.id
            ? 'text-towa-accent'
            : 'text-towa-text-muted hover:text-towa-text hover:bg-towa-surface-light'"
          :disabled="loading !== null"
          @click="runAction(action.id)"
        >
          <component :is="action.icon" :size="13" :class="{ 'animate-pulse': loading === action.id }" />
          {{ action.label }}
        </button>
      </div>

      <!-- Right: view mode + zoom -->
      <div class="flex items-center gap-2">
        <div class="flex items-center gap-0.5 bg-towa-surface rounded p-0.5">
          <button
            class="p-1 rounded transition-colors"
            :class="viewMode === 'single-split' ? 'bg-towa-surface-light text-towa-text' : 'text-towa-text-muted hover:text-towa-text'"
            title="한쪽보기"
            @click="setViewMode('single-split')"
          >
            <Columns2 :size="13" />
          </button>
          <button
            class="p-1 rounded transition-colors"
            :class="viewMode === 'spread' ? 'bg-towa-surface-light text-towa-text' : 'text-towa-text-muted hover:text-towa-text'"
            title="두쪽보기"
            @click="setViewMode('spread')"
          >
            <Square :size="13" />
          </button>
        </div>

        <div class="flex items-center gap-0.5">
          <button class="p-1 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-text transition-colors" @click="zoomOut">
            <ZoomOut :size="13" />
          </button>
          <span class="text-[11px] text-towa-text-muted w-9 text-center">{{ zoomLevel }}%</span>
          <button class="p-1 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-text transition-colors" @click="zoomIn">
            <ZoomIn :size="13" />
          </button>
        </div>
      </div>
    </div>

    <!-- Canvas area -->
    <div class="flex-1 overflow-auto bg-towa-bg">
      <!-- Single split -->
      <div v-if="viewMode === 'single-split' && currentPage" class="h-full flex">
        <div class="flex-1 flex items-center justify-center p-3 border-r border-towa-border">
          <div class="h-full flex flex-col items-center justify-center">
            <img
              :src="currentPage.originalImage"
              alt="원본"
              class="max-h-full max-w-full object-contain shadow-lg rounded"
              :style="{ transform: `scale(${zoomLevel / 100})`, transformOrigin: 'center center' }"
            />
            <div class="text-[10px] text-towa-text-muted mt-1 shrink-0">원본</div>
          </div>
        </div>
        <div class="flex-1 flex items-center justify-center p-3">
          <div class="h-full flex flex-col items-center justify-center">
            <img
              :src="currentPage.originalImage"
              alt="작업본"
              class="max-h-full max-w-full object-contain shadow-lg rounded"
              :style="{ transform: `scale(${zoomLevel / 100})`, transformOrigin: 'center center' }"
            />
            <div class="text-[10px] text-towa-text-muted mt-1 shrink-0">작업본</div>
          </div>
        </div>
      </div>

      <!-- Spread -->
      <div v-else-if="viewMode === 'spread'" class="h-full flex items-center justify-center gap-2 p-3">
        <div v-if="currentPage" class="h-full flex flex-col items-center justify-center">
          <img
            :src="currentPage.originalImage"
            :alt="`${currentPage.index}p`"
            class="max-h-full max-w-full object-contain shadow-lg rounded"
            :style="{ transform: `scale(${zoomLevel / 100})`, transformOrigin: 'center center' }"
          />
          <div class="text-[10px] text-towa-text-muted mt-1 shrink-0">{{ currentPage.index }}p</div>
        </div>
        <div v-if="adjacentPage" class="h-full flex flex-col items-center justify-center">
          <img
            :src="adjacentPage.originalImage"
            :alt="`${adjacentPage.index}p`"
            class="max-h-full max-w-full object-contain shadow-lg rounded"
            :style="{ transform: `scale(${zoomLevel / 100})`, transformOrigin: 'center center' }"
          />
          <div class="text-[10px] text-towa-text-muted mt-1 shrink-0">{{ adjacentPage.index }}p</div>
        </div>
      </div>

      <!-- No page -->
      <div v-else class="h-full flex items-center justify-center text-sm text-towa-text-muted">
        페이지를 선택하세요
      </div>
    </div>
  </div>
</template>
