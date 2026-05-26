<script setup lang="ts">
import type { Page } from '@/types/page'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-vue-next'

defineProps<{
  pages: Page[]
  currentPageId: string | null
  collapsed: boolean
}>()

defineEmits<{
  selectPage: [pageId: string]
  'update:collapsed': [value: boolean]
}>()

const statusColors: Record<string, string> = {
  'waiting': 'bg-gray-500',
  'ai-processing': 'bg-yellow-500',
  'in-progress': 'bg-towa-accent',
  'done': 'bg-green-500',
}
</script>

<template>
  <aside
    class="bg-towa-surface border-r border-towa-border flex flex-col shrink-0 h-full transition-all overflow-hidden"
    :class="collapsed ? 'w-10' : 'w-40'"
  >
    <!-- Toggle button -->
    <button
      class="p-2 text-towa-text-muted hover:text-towa-text transition-colors shrink-0 flex justify-center"
      @click="$emit('update:collapsed', !collapsed)"
    >
      <PanelLeftClose v-if="!collapsed" :size="16" />
      <PanelLeftOpen v-else :size="16" />
    </button>

    <!-- Page list -->
    <div class="flex-1 overflow-y-auto">
      <!-- Collapsed: page numbers only -->
      <div v-if="collapsed" class="flex flex-col items-center gap-1 py-1">
        <button
          v-for="page in pages"
          :key="page.id"
          class="w-7 h-7 rounded text-[10px] font-medium flex items-center justify-center transition-colors relative"
          :class="page.id === currentPageId
            ? 'bg-towa-accent text-white'
            : 'text-towa-text-muted hover:bg-towa-surface-light hover:text-towa-text'"
          @click="$emit('selectPage', page.id)"
        >
          {{ page.index }}
          <span
            class="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full"
            :class="statusColors[page.status] ?? 'bg-gray-500'"
          />
        </button>
      </div>

      <!-- Expanded: thumbnails + info -->
      <div v-else class="flex flex-col gap-1 p-2">
        <button
          v-for="page in pages"
          :key="page.id"
          class="rounded-md overflow-hidden border-2 transition-colors"
          :class="page.id === currentPageId
            ? 'border-towa-accent'
            : 'border-transparent hover:border-towa-surface-light'"
          @click="$emit('selectPage', page.id)"
        >
          <div class="relative">
            <img
              v-if="page.thumbnail"
              :src="page.thumbnail"
              :alt="`${page.index}p`"
              class="w-full aspect-[2/3] object-cover"
            />
            <div v-else class="w-full aspect-[2/3] bg-towa-bg flex items-center justify-center text-towa-text-muted text-xs">
              {{ page.index }}p
            </div>
            <span
              class="absolute top-1 right-1 text-[8px] font-medium text-white px-1 py-0.5 rounded"
              :class="statusColors[page.status] ?? 'bg-gray-500'"
            >
              {{ page.index }}p
            </span>
          </div>
        </button>
      </div>
    </div>
  </aside>
</template>
