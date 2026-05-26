<script setup lang="ts">
import { ref } from 'vue'
import { Folder, MoreHorizontal, FolderPlus, Pencil, Trash2 } from 'lucide-vue-next'
import BaseCard from '@/components/common/BaseCard.vue'

export interface PreviewItem {
  type: 'folder' | 'project'
  name: string
  thumbnail?: string
}

defineProps<{
  name: string
  itemCount: number
  previewItems: PreviewItem[]
  /** Whether the "Create subfolder" action should be enabled (depth check). */
  canAddChild?: boolean
}>()

const emit = defineEmits<{
  click: []
  createChild: []
  rename: []
  move: []
  delete: []
}>()

const menuOpen = ref(false)
function toggleMenu(ev: Event) {
  ev.stopPropagation()
  menuOpen.value = !menuOpen.value
}
function closeMenu() { menuOpen.value = false }
function pick(action: 'createChild' | 'rename' | 'move' | 'delete') {
  closeMenu()
  emit(action)
}
</script>

<template>
  <BaseCard hoverable class="group relative" @click="$emit('click')">
    <div class="aspect-[3/4] bg-towa-bg overflow-hidden relative">
      <!-- 2x2 preview grid (always 4 cells) -->
      <div class="grid grid-cols-2 grid-rows-2 gap-px h-full p-1 opacity-35 pointer-events-none">
        <div
          v-for="i in 4"
          :key="i"
          class="bg-towa-surface rounded-sm overflow-hidden flex items-center justify-center"
        >
          <template v-if="previewItems[i - 1]">
            <div v-if="previewItems[i - 1].type === 'folder'" class="flex flex-col items-center gap-0.5">
              <Folder :size="20" class="text-towa-accent" />
              <span class="text-[8px] text-towa-text-muted truncate max-w-full px-1">{{ previewItems[i - 1].name }}</span>
            </div>
            <img
              v-else-if="previewItems[i - 1].thumbnail"
              :src="previewItems[i - 1].thumbnail"
              :alt="previewItems[i - 1].name"
              class="w-full h-full object-contain"
            />
          </template>
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

      <!-- Action menu button on hover -->
      <div class="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity" :class="{ 'opacity-100': menuOpen }">
        <button
          class="p-1 rounded-md bg-black/60 text-white/80 hover:bg-towa-accent hover:text-white transition-colors"
          @click.stop="toggleMenu"
          title="폴더 작업"
        >
          <MoreHorizontal :size="14" />
        </button>
      </div>
    </div>

    <!-- Dropdown menu -->
    <div
      v-if="menuOpen"
      class="absolute top-9 right-1.5 bg-towa-surface-light border border-towa-border rounded shadow-lg py-1 text-xs z-10 min-w-[140px]"
      @click.stop
    >
      <button
        v-if="canAddChild !== false"
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-towa-text-muted hover:text-towa-text flex items-center gap-1.5"
        @click="pick('createChild')"
      >
        <FolderPlus :size="12" /> 하위 폴더
      </button>
      <button
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-towa-text-muted hover:text-towa-text flex items-center gap-1.5"
        @click="pick('rename')"
      >
        <Pencil :size="12" /> 이름 변경
      </button>
      <button
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-towa-text-muted hover:text-towa-text flex items-center gap-1.5"
        @click="pick('move')"
      >
        <Folder :size="12" /> 다른 폴더로 이동
      </button>
      <button
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-red-400 hover:text-red-300 flex items-center gap-1.5"
        @click="pick('delete')"
      >
        <Trash2 :size="12" /> 삭제
      </button>
    </div>

    <div class="px-3 py-2 flex items-center justify-between">
      <h3 class="text-sm font-medium text-towa-text truncate">{{ name }}</h3>
      <span class="text-xs text-towa-text-muted shrink-0 ml-2">{{ itemCount }}</span>
    </div>
  </BaseCard>
</template>
