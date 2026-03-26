<script setup lang="ts">
import { Folder } from 'lucide-vue-next'
import BaseCard from '@/components/common/BaseCard.vue'

export interface PreviewItem {
  type: 'folder' | 'project'
  name: string
  thumbnail?: string // only for projects
}

defineProps<{
  name: string
  itemCount: number
  previewItems: PreviewItem[]
}>()

defineEmits<{
  click: []
}>()
</script>

<template>
  <BaseCard hoverable @click="$emit('click')">
    <div class="aspect-[3/4] bg-towa-bg overflow-hidden relative">
      <!-- 2x2 preview grid (always 4 cells) -->
      <div class="grid grid-cols-2 grid-rows-2 gap-px h-full p-1 opacity-35">
        <div
          v-for="i in 4"
          :key="i"
          class="bg-towa-surface rounded-sm overflow-hidden flex items-center justify-center"
        >
          <template v-if="previewItems[i - 1]">
            <!-- Subfolder preview -->
            <div v-if="previewItems[i - 1].type === 'folder'" class="flex flex-col items-center gap-0.5">
              <Folder :size="20" class="text-towa-accent" />
              <span class="text-[8px] text-towa-text-muted truncate max-w-full px-1">{{ previewItems[i - 1].name }}</span>
            </div>
            <!-- Project thumbnail preview -->
            <img
              v-else-if="previewItems[i - 1].thumbnail"
              :src="previewItems[i - 1].thumbnail"
              :alt="previewItems[i - 1].name"
              class="w-full h-full object-contain"
            />
          </template>
          <!-- Empty cell -->
          <template v-else>
            <div class="w-full h-full" />
          </template>
        </div>
      </div>

      <!-- Folder icon overlay (center) -->
      <div class="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div class="bg-black/30 rounded-full p-3">
          <Folder :size="36" class="text-towa-accent drop-shadow" />
        </div>
      </div>
    </div>
    <div class="px-3 py-2 flex items-center justify-between">
      <h3 class="text-sm font-medium text-towa-text truncate">{{ name }}</h3>
      <span class="text-xs text-towa-text-muted shrink-0 ml-2">{{ itemCount }}</span>
    </div>
  </BaseCard>
</template>
