<script setup lang="ts">
import type { Project } from '@/types/project'
import type { FolderNode } from '@/types/folder'
import type { PreviewItem } from './FolderCard.vue'
import { Plus } from 'lucide-vue-next'
import ProjectCard from './ProjectCard.vue'
import FolderCard from './FolderCard.vue'

defineProps<{
  projects: Project[]
  subfolders: FolderNode[]
  folderPreviews: Record<string, { count: number; items: PreviewItem[] }>
}>()

const emit = defineEmits<{
  select: [project: Project]
  create: []
  openFolder: [folderId: string]
  deleteProject: [project: Project]
  moveProject: [project: Project]
  dropOnFolder: [folderId: string, projectId: string]
}>()

function onDragOver(ev: DragEvent) {
  if (!ev.dataTransfer) return
  if (Array.from(ev.dataTransfer.types).includes('application/x-towa-project-id')) {
    ev.dataTransfer.dropEffect = 'move'
  }
}

function onDropOnFolder(ev: DragEvent, folderId: string) {
  const id = ev.dataTransfer?.getData('application/x-towa-project-id')
  if (!id) return
  emit('dropOnFolder', folderId, id)
}
</script>

<template>
  <div class="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-4">
    <!-- Create new project -->
    <div
      class="bg-towa-surface border-2 border-dashed border-towa-border rounded-lg flex flex-col items-center justify-center gap-2 cursor-pointer hover:border-towa-accent hover:text-towa-accent text-towa-text-muted transition-colors overflow-hidden"
    >
      <div class="aspect-[3/4] flex flex-col items-center justify-center gap-2 w-full" @click="emit('create')">
        <Plus :size="32" />
        <span class="text-sm font-medium">새 프로젝트</span>
      </div>
    </div>

    <!-- Subfolders (drop target) -->
    <div
      v-for="folder in subfolders"
      :key="folder.id"
      @dragover.prevent="onDragOver"
      @drop.prevent="(ev) => onDropOnFolder(ev, folder.id)"
    >
      <FolderCard
        :name="folder.name"
        :item-count="folderPreviews[folder.id]?.count ?? 0"
        :preview-items="folderPreviews[folder.id]?.items ?? []"
        @click="emit('openFolder', folder.id)"
      />
    </div>

    <!-- Project cards -->
    <ProjectCard
      v-for="project in projects"
      :key="project.id"
      :project="project"
      @click="emit('select', project)"
      @delete="emit('deleteProject', project)"
      @move="emit('moveProject', project)"
    />
  </div>
</template>
