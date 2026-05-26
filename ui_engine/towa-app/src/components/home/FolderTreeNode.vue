<script setup lang="ts">
import { computed } from 'vue'
import { Folder, FolderOpen, ChevronRight, ChevronDown, MoreHorizontal, FolderPlus, Pencil, Trash2 } from 'lucide-vue-next'
import type { FolderNode } from '@/types/folder'
import { MAX_FOLDER_DEPTH } from '@/types/folder'

const props = defineProps<{
  folder: FolderNode
  expanded: Set<string>
  currentFolderId: string | null
  menuFolderId: string | null
  level: number
}>()

const emit = defineEmits<{
  toggle: [folderId: string]
  navigate: [folderId: string | null]
  openMenu: [folderId: string, ev: Event]
  createChild: [parentId: string]
  rename: [folderId: string]
  delete: [folderId: string]
  move: [folderId: string]
  dropProject: [folderId: string, projectId: string]
}>()

function onDragOver(ev: DragEvent) {
  if (!ev.dataTransfer) return
  if (Array.from(ev.dataTransfer.types).includes('application/x-towa-project-id')) {
    ev.dataTransfer.dropEffect = 'move'
  }
}
function onDrop(ev: DragEvent) {
  const projectId = ev.dataTransfer?.getData('application/x-towa-project-id')
  if (!projectId) return
  emit('dropProject', props.folder.id, projectId)
}

const isOpen = computed(() => props.expanded.has(props.folder.id))
const isActive = computed(() => props.currentFolderId === props.folder.id)
const isMenuOpen = computed(() => props.menuFolderId === props.folder.id)
const hasChildren = computed(() => props.folder.children.length > 0)
const canAddChild = computed(() => props.level + 1 < MAX_FOLDER_DEPTH)

const indentPx = computed(() => `${8 + props.level * 12}px`)
</script>

<template>
  <div>
    <div
      class="flex items-center group rounded"
      :class="isActive ? 'bg-towa-accent/15' : 'hover:bg-towa-surface-light'"
      :style="{ paddingLeft: indentPx }"
      @dragover.prevent="onDragOver"
      @drop.prevent="onDrop"
    >
      <button
        v-if="hasChildren"
        class="p-0.5 text-towa-text-muted hover:text-towa-text shrink-0"
        @click="emit('toggle', folder.id)"
      >
        <ChevronDown v-if="isOpen" :size="12" />
        <ChevronRight v-else :size="12" />
      </button>
      <span v-else class="w-4 shrink-0" />

      <button
        class="flex-1 text-left text-sm py-1.5 flex items-center gap-1.5 min-w-0"
        :class="isActive ? 'text-towa-accent' : 'text-towa-text-muted hover:text-towa-text'"
        @click="emit('navigate', folder.id)"
      >
        <FolderOpen v-if="isActive" :size="14" />
        <Folder v-else :size="14" />
        <span class="truncate">{{ folder.name }}</span>
      </button>

      <button
        class="p-1 text-towa-text-muted hover:text-towa-text opacity-0 group-hover:opacity-100 transition-opacity"
        :class="{ 'opacity-100': isMenuOpen }"
        @click="emit('openMenu', folder.id, $event)"
      >
        <MoreHorizontal :size="14" />
      </button>
    </div>

    <!-- Action menu (popover) -->
    <div
      v-if="isMenuOpen"
      class="bg-towa-surface-light border border-towa-border rounded shadow-lg py-1 ml-6 mt-0.5 text-xs"
      @click.stop
    >
      <button
        v-if="canAddChild"
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-towa-text-muted hover:text-towa-text flex items-center gap-1.5"
        @click="emit('createChild', folder.id)"
      >
        <FolderPlus :size="12" /> 하위 폴더
      </button>
      <button
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-towa-text-muted hover:text-towa-text flex items-center gap-1.5"
        @click="emit('rename', folder.id)"
      >
        <Pencil :size="12" /> 이름 변경
      </button>
      <button
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-towa-text-muted hover:text-towa-text flex items-center gap-1.5"
        @click="emit('move', folder.id)"
      >
        <Folder :size="12" /> 다른 폴더로 이동
      </button>
      <button
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-red-400 hover:text-red-300 flex items-center gap-1.5"
        @click="emit('delete', folder.id)"
      >
        <Trash2 :size="12" /> 삭제
      </button>
    </div>

    <!-- Recursive children -->
    <template v-if="isOpen && hasChildren">
      <FolderTreeNode
        v-for="child in folder.children"
        :key="child.id"
        :folder="child"
        :expanded="expanded"
        :current-folder-id="currentFolderId"
        :menu-folder-id="menuFolderId"
        :level="level + 1"
        @toggle="(id) => emit('toggle', id)"
        @navigate="(id) => emit('navigate', id)"
        @open-menu="(id, ev) => emit('openMenu', id, ev)"
        @create-child="(id) => emit('createChild', id)"
        @rename="(id) => emit('rename', id)"
        @delete="(id) => emit('delete', id)"
        @move="(id) => emit('move', id)"
        @drop-project="(fid, pid) => emit('dropProject', fid, pid)"
      />
    </template>
  </div>
</template>
