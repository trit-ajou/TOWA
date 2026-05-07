<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import type { Project, ProjectStatus } from '@/types/project'
import type { FolderNode } from '@/types/folder'
import type { PreviewItem } from '@/components/home/FolderCard.vue'
import { useModal } from '@/composables/useModal'
import { createUlid } from '@/utils/ulid'
import { buildPageSnapshotFromFile } from '@/utils/page-from-file'
import HomeSidebar from '@/components/home/HomeSidebar.vue'
import ProjectGrid from '@/components/home/ProjectGrid.vue'
import CreateProjectModal from '@/components/home/CreateProjectModal.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import BaseButton from '@/components/common/BaseButton.vue'

const store = useStore()
const router = useRouter()
const createModal = useModal()
const deleteModal = useModal()
const projectToDelete = ref<Project | null>(null)

const currentPath = computed<string[]>(() => store.getters['library/currentPath'])
const statusFilter = computed<ProjectStatus | 'all'>(() => store.getters['library/statusFilter'])
const subfolders = computed<FolderNode[]>(() => store.getters['library/currentSubfolders'])
const folderPathStr = computed(() => currentPath.value.join('/') || null)

const statusOptions = [
  { value: 'all' as const, label: '전체' },
  { value: 'in-progress' as const, label: '진행중' },
  { value: 'done' as const, label: '완료' },
  { value: 'todo' as const, label: 'TODO' },
]

function setStatusFilter(filter: ProjectStatus | 'all') {
  store.commit('library/SET_STATUS_FILTER', filter)
}

const allProjects = computed<Project[]>(() => store.getters['projects/all'])

// Only projects whose folder EXACTLY matches current path
const projectsHere = computed(() => {
  const path = folderPathStr.value
  let filtered: Project[]

  if (!path) {
    filtered = allProjects.value.filter((p) => !p.folder)
  } else {
    filtered = allProjects.value.filter((p) => p.folder === path)
  }

  if (statusFilter.value !== 'all') {
    filtered = filtered.filter((p) => p.status === statusFilter.value)
  }

  return filtered
})

// Preview: direct children only (subfolders first, then direct projects), max 4
const folderPreviews = computed(() => {
  const previews: Record<string, { count: number; items: PreviewItem[] }> = {}
  const basePath = folderPathStr.value

  for (const folder of subfolders.value) {
    const subPath = basePath ? `${basePath}/${folder.name}` : folder.name
    const items: PreviewItem[] = []

    // Add child subfolders first
    for (const child of folder.children) {
      items.push({ type: 'folder', name: child.name })
    }

    // Add direct projects in this folder (exact match)
    const directProjects = allProjects.value.filter((p) => p.folder === subPath)
    for (const proj of directProjects) {
      items.push({ type: 'project', name: proj.name, thumbnail: proj.thumbnail })
    }

    // Total count = subfolders + direct projects
    const totalCount = folder.children.length + directProjects.length

    previews[folder.name] = {
      count: totalCount,
      items: items.slice(0, 4),
    }
  }

  return previews
})

function navigateToFolder(folderName: string) {
  store.commit('library/NAVIGATE_INTO', folderName)
}

function selectProject(project: Project) {
  store.commit('editor/SET_CURRENT_PROJECT', project.id)
  store.commit('editor/SET_ACTIVE_TAB', 'home')
  store.commit('editor/SET_SELECTED_PAGE', null)
  router.push(`/project/${project.id}`)
}

async function createProject(form: { name: string; sourceLang: string; targetLang: string; autoDetect: boolean; autoInpaint: boolean; autoTranslate: boolean; inferenceMode: 'local' | 'cloud'; files: File[] }) {
  const projectId = createUlid()
  const newProject: Project = {
    id: projectId,
    name: form.name,
    thumbnail: `https://placehold.co/400x560/1e1e32/0db0bc?text=${encodeURIComponent(form.name)}`,
    sourceLang: form.sourceLang,
    targetLang: form.targetLang,
    pageCount: 0,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    status: 'todo',
    folder: folderPathStr.value ?? '',
    config: {
      autoDetect: form.autoDetect,
      autoInpaint: form.autoInpaint,
      autoTranslate: form.autoTranslate,
      inferenceMode: form.inferenceMode,
    },
  }
  await store.dispatch('projects/create', newProject)

  for (let i = 0; i < form.files.length; i++) {
    const snapshot = await buildPageSnapshotFromFile(form.files[i], projectId, i + 1)
    await store.dispatch('pages/addPage', { projectId, snapshot })
  }
  if (form.files.length > 0) {
    await store.dispatch('projects/update', {
      ...newProject,
      pageCount: form.files.length,
      updatedAt: new Date().toISOString(),
    })
  }

  createModal.close()
  store.commit('editor/SET_CURRENT_PROJECT', projectId)
  store.commit('editor/SET_ACTIVE_TAB', 'home')
  store.commit('editor/SET_SELECTED_PAGE', null)
  router.push(`/project/${projectId}`)
}

function confirmDeleteProject(project: Project) {
  projectToDelete.value = project
  deleteModal.open()
}

async function deleteProject() {
  if (!projectToDelete.value) return
  await store.dispatch('projects/remove', projectToDelete.value.id)
  deleteModal.close()
  projectToDelete.value = null
}
</script>

<template>
  <div class="flex h-[calc(100vh-48px)]">
    <HomeSidebar />
    <main class="flex-1 p-6 overflow-y-auto">
      <!-- Status filter chips -->
      <div class="flex items-center justify-end mb-4">
        <div class="flex items-center gap-1 bg-towa-surface rounded-lg p-0.5">
          <button
            v-for="opt in statusOptions"
            :key="opt.value"
            class="px-2.5 py-1 text-xs rounded-md transition-colors"
            :class="statusFilter === opt.value
              ? 'bg-towa-surface-light text-towa-text font-medium'
              : 'text-towa-text-muted hover:text-towa-text'"
            @click="setStatusFilter(opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>

      <ProjectGrid
        :projects="projectsHere"
        :subfolders="subfolders"
        :folder-previews="folderPreviews"
        @select="selectProject"
        @create="createModal.open()"
        @open-folder="navigateToFolder"
        @delete-project="confirmDeleteProject"
      />
    </main>

    <CreateProjectModal
      :open="createModal.isOpen.value"
      @close="createModal.close()"
      @create="createProject"
    />

    <BaseModal
      title="프로젝트 삭제"
      :open="deleteModal.isOpen.value"
      @close="deleteModal.close()"
    >
      <p class="text-sm text-towa-text-muted">
        <span class="font-medium text-towa-text">{{ projectToDelete?.name }}</span>
        프로젝트를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.
      </p>
      <template #footer>
        <BaseButton variant="secondary" size="sm" @click="deleteModal.close()">취소</BaseButton>
        <BaseButton variant="danger" size="sm" @click="deleteProject">삭제</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>
