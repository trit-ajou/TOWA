<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import type { Project, ProjectStatus } from '@/types/project'
import type { Folder, FolderNode } from '@/types/folder'
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

const currentFolderId = computed<string | null>(() => store.getters['library/currentFolderId'])
const statusFilter = computed<ProjectStatus | 'all'>(() => store.getters['library/statusFilter'])
const searchQuery = computed<string>(() => store.getters['library/searchQuery'])

const allProjects = computed<Project[]>(() => store.getters['projects/all'])
const allFolders = computed<Folder[]>(() => store.getters['folders/all'])
const childrenOf = computed(() => store.getters['folders/childrenOf'] as (parentId: string | null) => Folder[])
const currentFolder = computed<Folder | undefined>(() =>
  currentFolderId.value ? (store.getters['folders/byId'](currentFolderId.value) as Folder | undefined) : undefined,
)
const folderPath = computed<string>(() =>
  currentFolderId.value ? (store.getters['folders/pathOf'](currentFolderId.value) as string) : '',
)

const statusOptions = [
  { value: 'all' as const, label: '전체' },
  { value: 'in-progress' as const, label: '진행중' },
  { value: 'done' as const, label: '완료' },
  { value: 'todo' as const, label: 'TODO' },
]

function setStatusFilter(filter: ProjectStatus | 'all') {
  store.commit('library/SET_STATUS_FILTER', filter)
}

const subfolders = computed<FolderNode[]>(() =>
  childrenOf.value(currentFolderId.value).map((f) => ({
    id: f.id,
    name: f.name,
    parentId: f.parentId,
    children: childrenOf.value(f.id).map((c) => ({ id: c.id, name: c.name, parentId: c.parentId, children: [] })),
  })),
)

const projectsHere = computed<Project[]>(() => {
  let list = allProjects.value.filter((p) => (p.folderId ?? null) === currentFolderId.value)
  if (statusFilter.value !== 'all') list = list.filter((p) => p.status === statusFilter.value)
  const q = searchQuery.value.trim().toLowerCase()
  if (q) list = list.filter((p) => p.name.toLowerCase().includes(q))
  return list
})

const folderPreviews = computed(() => {
  const previews: Record<string, { count: number; items: PreviewItem[] }> = {}
  for (const folder of subfolders.value) {
    const items: PreviewItem[] = []
    for (const child of folder.children) {
      items.push({ type: 'folder', name: child.name })
    }
    const directProjects = allProjects.value.filter((p) => p.folderId === folder.id)
    for (const proj of directProjects) {
      items.push({ type: 'project', name: proj.name, thumbnail: proj.thumbnail })
    }
    previews[folder.id] = {
      count: folder.children.length + directProjects.length,
      items: items.slice(0, 4),
    }
  }
  return previews
})

function navigateToFolder(folderId: string | null) {
  store.commit('library/SET_CURRENT_FOLDER', folderId)
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
    folderId: currentFolderId.value,
    folderPath: folderPath.value || null,
    deletedAt: null,
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
      <!-- Breadcrumb + Status filter chips -->
      <div class="flex items-center justify-between mb-4">
        <div class="text-sm text-towa-text-muted">
          <span v-if="currentFolder">{{ folderPath }}</span>
          <span v-else>전체</span>
        </div>
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
        프로젝트를 휴지통으로 옮깁니다.
      </p>
      <template #footer>
        <BaseButton variant="secondary" size="sm" @click="deleteModal.close()">취소</BaseButton>
        <BaseButton variant="danger" size="sm" @click="deleteProject">삭제</BaseButton>
      </template>
    </BaseModal>
  </div>
</template>
