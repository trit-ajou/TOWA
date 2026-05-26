<script setup lang="ts">
import { computed } from 'vue'
import { Folder, FolderOpen, ChevronRight, ChevronDown } from 'lucide-vue-next'
import type { FolderNode } from '@/types/folder'

const props = defineProps<{
  folder: FolderNode
  expanded: Set<string>
  selectedId: string | null
  disabledIds?: Set<string>
  level: number
}>()

const emit = defineEmits<{
  toggle: [id: string]
  pick: [id: string | null]
}>()

const isOpen = computed(() => props.expanded.has(props.folder.id))
const isSelected = computed(() => props.selectedId === props.folder.id)
const hasChildren = computed(() => props.folder.children.length > 0)
const isDisabled = computed(() => props.disabledIds?.has(props.folder.id) ?? false)

const indentPx = computed(() => `${8 + props.level * 12}px`)
</script>

<template>
  <div>
    <div
      class="flex items-center rounded"
      :class="[
        isSelected ? 'bg-towa-accent/15' : (isDisabled ? '' : 'hover:bg-towa-surface'),
        isDisabled ? 'opacity-40 cursor-not-allowed' : '',
      ]"
      :style="{ paddingLeft: indentPx }"
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
        :class="isSelected ? 'text-towa-accent' : 'text-towa-text-muted hover:text-towa-text'"
        :disabled="isDisabled"
        @click="emit('pick', folder.id)"
      >
        <FolderOpen v-if="isSelected" :size="14" />
        <Folder v-else :size="14" />
        <span class="truncate">{{ folder.name }}</span>
      </button>
    </div>

    <template v-if="isOpen && hasChildren">
      <FolderPickerNode
        v-for="child in folder.children"
        :key="child.id"
        :folder="child"
        :expanded="expanded"
        :selected-id="selectedId"
        :disabled-ids="disabledIds"
        :level="level + 1"
        @toggle="(id) => emit('toggle', id)"
        @pick="(id) => emit('pick', id)"
      />
    </template>
  </div>
</template>
