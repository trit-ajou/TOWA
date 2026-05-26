<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { Plus, FilePlus, FolderPlus } from 'lucide-vue-next'

const emit = defineEmits<{
  createProject: []
  createFolder: []
}>()

defineProps<{
  /** Render the trigger as a large grid tile (matches FolderCard / ProjectCard size). */
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
  <div class="relative inline-block" data-add-menu>
    <!-- Tile trigger (grid placeholder) -->
    <div
      v-if="variant === 'tile'"
      class="bg-towa-surface border-2 border-dashed border-towa-border rounded-lg flex flex-col items-center justify-center gap-2 cursor-pointer hover:border-towa-accent hover:text-towa-accent text-towa-text-muted transition-colors overflow-hidden"
      @click="toggle"
    >
      <div class="aspect-[3/4] flex flex-col items-center justify-center gap-2 w-full">
        <Plus :size="32" />
        <span class="text-sm font-medium">{{ label ?? '추가' }}</span>
      </div>
    </div>

    <!-- Toolbar trigger (rounded button) -->
    <button
      v-else-if="variant === 'toolbar'"
      class="flex items-center gap-1 px-3 py-1.5 rounded-md bg-towa-accent text-white text-sm font-medium hover:bg-towa-accent-hover transition-colors"
      @click="toggle"
    >
      <Plus :size="14" />
      <span>{{ label ?? '추가' }}</span>
    </button>

    <!-- Default: small icon button -->
    <button
      v-else
      class="p-1 text-towa-text-muted hover:text-towa-accent rounded transition-colors"
      :title="label ?? '추가'"
      @click="toggle"
    >
      <Plus :size="14" />
    </button>

    <!-- Menu -->
    <div
      v-if="open"
      class="absolute right-0 mt-1 bg-towa-surface-light border border-towa-border rounded shadow-lg py-1 text-xs z-20 min-w-[140px]"
      :class="variant === 'tile' ? 'top-12 left-1/2 -translate-x-1/2 right-auto' : ''"
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
