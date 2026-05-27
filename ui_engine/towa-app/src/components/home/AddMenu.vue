<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import { Plus, FilePlus, FolderPlus } from 'lucide-vue-next'
import BaseCard from '@/components/common/BaseCard.vue'

const emit = defineEmits<{
  createProject: []
  createFolder: []
}>()

defineProps<{
  /** Render variant. tile = grid card; toolbar = pill button; icon-button = small +. */
  variant?: 'icon-button' | 'tile' | 'toolbar'
  label?: string
}>()

const open = ref(false)
const popX = ref(0)
const popY = ref(0)

function openAtEvent(ev: MouseEvent) {
  ev.stopPropagation()
  popX.value = ev.clientX
  popY.value = ev.clientY
  open.value = true
}

function openAtElement(ev: Event) {
  ev.stopPropagation()
  const el = ev.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  popX.value = rect.right
  popY.value = rect.bottom + 4
  open.value = true
}

function close() { open.value = false }

function onDocClick(ev: MouseEvent) {
  if (!open.value) return
  const target = ev.target as HTMLElement | null
  if (target?.closest('[data-add-popover]')) return
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
  <!-- Tile: matches FolderCard/ProjectCard size, single + glyph -->
  <BaseCard v-if="variant === 'tile'" hoverable @click="openAtEvent($event)">
    <div class="aspect-[3/4] flex items-center justify-center text-towa-text-muted hover:text-towa-accent transition-colors">
      <Plus :size="40" />
    </div>
    <div class="px-3 py-2">
      <h3 class="text-sm font-medium text-towa-text-muted">{{ label ?? '추가' }}</h3>
    </div>
  </BaseCard>

  <!-- Toolbar: pill button -->
  <button
    v-else-if="variant === 'toolbar'"
    class="flex items-center gap-1 px-3 py-1.5 rounded-md bg-towa-accent text-white text-sm font-medium hover:bg-towa-accent-hover transition-colors"
    @click="openAtElement($event)"
  >
    <Plus :size="14" />
    <span>{{ label ?? '추가' }}</span>
  </button>

  <!-- icon-button (sidebar): small + -->
  <button
    v-else
    class="p-1 text-towa-text-muted hover:text-towa-accent rounded transition-colors"
    :title="label ?? '추가'"
    @click="openAtElement($event)"
  >
    <Plus :size="14" />
  </button>

  <!-- Popover (teleported to viewport by fixed positioning) -->
  <Teleport to="body">
    <div
      v-if="open"
      data-add-popover
      class="fixed bg-towa-surface-light border border-towa-border rounded shadow-lg py-1 text-xs z-50 min-w-[140px]"
      :style="{ left: popX + 'px', top: popY + 'px', transform: 'translate(-50%, 4px)' }"
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
  </Teleport>
</template>
