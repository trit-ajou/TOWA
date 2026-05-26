<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { Plus, FilePlus, FolderPlus } from 'lucide-vue-next'
import BaseCard from '@/components/common/BaseCard.vue'

const emit = defineEmits<{
  createProject: []
  createFolder: []
}>()

defineProps<{
  /** Render variant. tile fills a grid slot; toolbar/icon-button use a dropdown menu. */
  variant?: 'icon-button' | 'tile' | 'toolbar'
  label?: string
}>()

const open = ref(false)
function toggle(ev: Event) {
  ev.stopPropagation()
  open.value = !open.value
}
function close() { open.value = false }

function onDocClick(ev: MouseEvent) {
  if (!open.value) return
  const target = ev.target as HTMLElement | null
  if (target?.closest('[data-add-menu]')) return
  close()
}
window.addEventListener('click', onDocClick)
onBeforeUnmount(() => window.removeEventListener('click', onDocClick))

function pick(action: 'createProject' | 'createFolder') {
  close()
  emit(action)
}
</script>

<template>
  <!-- Tile variant: full-size grid card with two click zones, no dropdown -->
  <BaseCard v-if="variant === 'tile'" class="group">
    <div class="aspect-[3/4] flex flex-col">
      <button
        class="flex-1 flex flex-col items-center justify-center gap-2 text-towa-text-muted hover:bg-towa-surface-light hover:text-towa-accent transition-colors border-b border-dashed border-towa-border"
        @click="emit('createProject')"
      >
        <FilePlus :size="24" />
        <span class="text-xs font-medium">새 프로젝트</span>
      </button>
      <button
        class="flex-1 flex flex-col items-center justify-center gap-2 text-towa-text-muted hover:bg-towa-surface-light hover:text-towa-accent transition-colors"
        @click="emit('createFolder')"
      >
        <FolderPlus :size="24" />
        <span class="text-xs font-medium">새 폴더</span>
      </button>
    </div>
    <div class="px-3 py-2">
      <h3 class="text-sm font-medium text-towa-text-muted">추가</h3>
    </div>
  </BaseCard>

  <!-- Toolbar variant: pill button + dropdown -->
  <div v-else-if="variant === 'toolbar'" class="relative inline-block" data-add-menu>
    <button
      class="flex items-center gap-1 px-3 py-1.5 rounded-md bg-towa-accent text-white text-sm font-medium hover:bg-towa-accent-hover transition-colors"
      @click="toggle"
    >
      <Plus :size="14" />
      <span>{{ label ?? '추가' }}</span>
    </button>
    <div
      v-if="open"
      class="absolute right-0 mt-1 bg-towa-surface-light border border-towa-border rounded shadow-lg py-1 text-xs z-20 min-w-[140px]"
      @click.stop
    >
      <button
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-towa-text-muted hover:text-towa-text flex items-center gap-1.5"
        @click="pick('createProject')"
      >
        <FilePlus :size="12" /> 새 프로젝트
      </button>
      <button
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-towa-text-muted hover:text-towa-text flex items-center gap-1.5"
        @click="pick('createFolder')"
      >
        <FolderPlus :size="12" /> 새 폴더
      </button>
    </div>
  </div>

  <!-- icon-button variant (sidebar): small + with dropdown -->
  <div v-else class="relative inline-block" data-add-menu>
    <button
      class="p-1 text-towa-text-muted hover:text-towa-accent rounded transition-colors"
      :title="label ?? '추가'"
      @click="toggle"
    >
      <Plus :size="14" />
    </button>
    <div
      v-if="open"
      class="absolute right-0 mt-1 bg-towa-surface-light border border-towa-border rounded shadow-lg py-1 text-xs z-20 min-w-[140px]"
      @click.stop
    >
      <button
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-towa-text-muted hover:text-towa-text flex items-center gap-1.5"
        @click="pick('createProject')"
      >
        <FilePlus :size="12" /> 새 프로젝트
      </button>
      <button
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-towa-text-muted hover:text-towa-text flex items-center gap-1.5"
        @click="pick('createFolder')"
      >
        <FolderPlus :size="12" /> 새 폴더
      </button>
    </div>
  </div>
</template>
