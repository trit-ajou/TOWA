<script setup lang="ts">
import { Plus, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import type { Layer, Text } from '@bitmappery/definitions/document'
import TextBlockItem from './TextBlockItem.vue'

defineProps<{
  layers: Layer[]
  selectedLayerId: string | null
  currentPageIndex: number
  totalPages: number
}>()

defineEmits<{
  selectLayer: [id: string]
  updateText: [layerId: string, textPatch: Partial<Text>]
  addBlock: []
  removeBlock: [layerId: string]
  prevPage: []
  nextPage: []
}>()
</script>

<template>
  <aside class="w-[320px] bg-towa-surface border-l border-towa-border flex flex-col shrink-0">
    <div class="px-3 py-2 border-b border-towa-border flex items-center justify-between">
      <h3 class="text-xs font-semibold text-towa-text-muted uppercase tracking-wider">
        번역 ({{ layers.length }})
      </h3>
      <button
        class="p-1 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-accent transition-colors"
        title="텍스트 블록 추가"
        @click="$emit('addBlock')"
      >
        <Plus :size="14" />
      </button>
    </div>
    <div class="flex-1 overflow-y-auto">
      <TextBlockItem
        v-for="layer in layers"
        :key="layer.id"
        :layer="layer"
        :selected="layer.id === selectedLayerId"
        @select="$emit('selectLayer', layer.id)"
        @update-text="(patch) => $emit('updateText', layer.id, patch)"
        @remove="$emit('removeBlock', layer.id)"
      />
      <div v-if="layers.length === 0" class="p-4 text-center text-sm text-towa-text-muted">
        텍스트 블록이 없습니다
      </div>
    </div>

    <!-- Page navigation -->
    <div class="px-3 py-2.5 border-t border-towa-border flex items-center justify-between shrink-0">
      <button
        class="flex items-center gap-1 px-2 py-1.5 rounded-md hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-text transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        :disabled="currentPageIndex <= 1"
        @click="$emit('prevPage')"
      >
        <ChevronLeft :size="16" />
        <span class="text-sm">이전</span>
        <kbd class="text-[10px] px-1 py-0.5 rounded bg-towa-bg border border-towa-border text-towa-text-muted">Q</kbd>
      </button>
      <span class="text-xs text-towa-text-muted">
        <span class="text-sm text-towa-text font-medium">{{ currentPageIndex }}</span> / {{ totalPages }} 페이지
      </span>
      <button
        class="flex items-center gap-1 px-2 py-1.5 rounded-md hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-text transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        :disabled="currentPageIndex >= totalPages"
        @click="$emit('nextPage')"
      >
        <span class="text-sm">다음</span>
        <kbd class="text-[10px] px-1 py-0.5 rounded bg-towa-bg border border-towa-border text-towa-text-muted">W</kbd>
        <ChevronRight :size="16" />
      </button>
    </div>
  </aside>
</template>
