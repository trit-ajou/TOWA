<script setup lang="ts">
import { computed } from 'vue'
import type { Page } from '@/types/page'
import { Edit3, Paintbrush } from 'lucide-vue-next'

const props = defineProps<{
  page: Page
  selected: boolean
}>()

defineEmits<{
  openEdit: []
  openDetail: []
}>()

const statusConfig = computed(() => {
  const map: Record<string, { label: string; color: string }> = {
    'waiting': { label: '대기', color: 'bg-gray-500' },
    'ai-processing': { label: 'AI 처리중', color: 'bg-yellow-500' },
    'in-progress': { label: '작업중', color: 'bg-towa-accent' },
    'done': { label: '완료', color: 'bg-green-500' },
  }
  return map[props.page.status] ?? map.waiting
})
</script>

<template>
  <div
    class="group relative bg-towa-surface border-2 rounded-lg overflow-hidden transition-all"
    :class="selected ? 'border-towa-accent' : 'border-towa-border hover:border-towa-surface-light'"
  >
    <div class="relative aspect-[2/3] bg-towa-bg overflow-hidden">
      <img
        :src="page.thumbnail"
        :alt="`페이지 ${page.index}`"
        class="w-full h-full object-cover"
      />
      <span
        class="absolute top-2 right-2 text-[10px] font-medium text-white px-1.5 py-0.5 rounded-full"
        :class="statusConfig.color"
      >
        {{ statusConfig.label }}
      </span>

      <!-- Hover overlay with buttons (same size) -->
      <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2">
        <button
          class="w-28 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md bg-towa-accent text-white text-xs font-medium hover:bg-towa-accent-hover transition-colors"
          @click.stop="$emit('openEdit')"
        >
          <Edit3 :size="12" />
          편집
        </button>
        <button
          class="w-28 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md bg-towa-surface-light text-towa-text text-xs font-medium hover:bg-towa-border transition-colors"
          @click.stop="$emit('openDetail')"
        >
          <Paintbrush :size="12" />
          상세 편집
        </button>
      </div>
    </div>
    <div class="p-2 text-center">
      <span class="text-xs text-towa-text-muted">{{ page.index }}p</span>
    </div>
  </div>
</template>
