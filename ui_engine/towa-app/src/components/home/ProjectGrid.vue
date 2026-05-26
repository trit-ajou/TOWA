<script setup lang="ts">
import type { Project } from '@/types/project'
import type { FolderNode } from '@/types/folder'
import type { PreviewItem } from './FolderCard.vue'
import ProjectCard from './ProjectCard.vue'
import FolderCard from './FolderCard.vue'
import AddMenu from './AddMenu.vue'

defineProps<{
  projects: Project[]
  subfolders: FolderNode[]
  folderPreviews: Record<string, { count: number; items: PreviewItem[] }>
}>()

const emit = defineEmits<{
  select: [project: Project]
  createProject: []
  createFolder: []
  openFolder: [folderId: string]
  deleteProject: [project: Project]
  moveProject: [project: Project]
  dropOnFolder: [folderId: string, projectId: string]
  folderCreateChild: [folderId: string]
  folderRename: [folderId: string]
  folderMove: [folderId: string]
  folderDelete: [folderId: string]
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
        @create-child="emit('folderCreateChild', folder.id)"
        @rename="emit('folderRename', folder.id)"
        @move="emit('folderMove', folder.id)"
        @delete="emit('folderDelete', folder.id)"
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

    <!-- Add tile (last index) -->
    <AddMenu
      variant="tile"
      label="추가"
      @create-project="emit('createProject')"
      @create-folder="emit('createFolder')"
    />
  </div>
</template>
