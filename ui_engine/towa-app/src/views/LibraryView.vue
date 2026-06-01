<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import type { Project, ProjectStatus } from '@/types/project'
import type { Folder, FolderNode } from '@/types/folder'
import type { PreviewItem } from '@/components/home/FolderCard.vue'
import { useModal } from '@/composables/useModal'
import { useProjects } from '@/composables/useProjects'
import { useFolders } from '@/composables/useFolders'
import { usePages } from '@/composables/usePages'
import { createUlid } from '@/utils/ulid'
import { buildPageSnapshotFromFile } from '@/utils/page-from-file'
import HomeSidebar from '@/components/home/HomeSidebar.vue'
import ProjectGrid from '@/components/home/ProjectGrid.vue'
import CreateProjectModal from '@/components/home/CreateProjectModal.vue'
import MoveToFolderModal from '@/components/home/MoveToFolderModal.vue'
import AddMenu from '@/components/home/AddMenu.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import { ChevronLeft } from 'lucide-vue-next'

const store = useStore()
const router = useRouter()
const projectsApi = useProjects()
const foldersApi = useFolders()
const createModal = useModal()
const deleteModal = useModal()
const moveModal = useModal()
const projectToDelete = ref<Project | null>(null)
const projectToMove = ref<Project | null>(null)

interface SidebarApi {
  openCreateModal: (parentId: string | null) => void
  openRenameModal: (folderId: string) => void
  openDeleteDialog: (folderId: string) => void
  openMoveFolderModal: (folderId: string) => void
}
const sidebar = ref<SidebarApi | null>(null)

function onFolderCreateChild(folderId: string) { sidebar.value?.openCreateModal(folderId) }
function onFolderRename(folderId: string) { sidebar.value?.openRenameModal(folderId) }
function onFolderMove(folderId: string) { sidebar.value?.openMoveFolderModal(folderId) }
function onFolderDelete(folderId: string) { sidebar.value?.openDeleteDialog(folderId) }

const currentFolderId = computed<string | null>(() => store.getters['library/currentFolderId'])
const statusFilter = computed<ProjectStatus | 'all'>(() => store.getters['library/statusFilter'])
const searchQuery = computed<string>(() => store.getters['library/searchQuery'])

const allProjects = projectsApi.all
const currentFolder = computed<Folder | undefined>(() =>
  currentFolderId.value ? foldersApi.byId(currentFolderId.value) : undefined,
)
const folderPath = computed<string>(() =>
  currentFolderId.value ? foldersApi.pathOf(currentFolderId.value) : '',
)

// usePages 인스턴스를 동적으로 만들기 위한 helper. addPage 시 active project 기준.
const pagesProjectIdForCreate = ref<string>('')
const pagesForCreate = usePages(pagesProjectIdForCreate)

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
  foldersApi.childrenOf(currentFolderId.value).map((f) => ({
    id: f.id,
    name: f.name,
    parentId: f.parentId,
    children: foldersApi.childrenOf(f.id).map((c) => ({ id: c.id, name: c.name, parentId: c.parentId, children: [] })),
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
  await projectsApi.create(newProject)

  pagesProjectIdForCreate.value = projectId
  for (let i = 0; i < form.files.length; i++) {
    const snapshot = await buildPageSnapshotFromFile(form.files[i], projectId, i + 1)
    await pagesForCreate.addPage({ projectId, snapshot })
  }
  if (form.files.length > 0) {
    await projectsApi.update({
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
  await projectsApi.remove(projectToDelete.value.id)
  deleteModal.close()
  projectToDelete.value = null
}

function openMoveModal(project: Project) {
  projectToMove.value = project
  moveModal.open()
}

async function submitMove(folderId: string | null) {
  if (!projectToMove.value) return
  await projectsApi.update({ ...projectToMove.value, folderId })
  moveModal.close()
  projectToMove.value = null
}

async function onDropOnFolder(folderId: string, projectId: string) {
  const project = projectsApi.byId(projectId)
  if (!project) return
  if ((project.folderId ?? null) === folderId) return
  await projectsApi.update({ ...project, folderId })
}

function goToParent() {
  const cur = currentFolder.value
  store.commit('library/SET_CURRENT_FOLDER', cur?.parentId ?? null)
}

/** + 메뉴 → 새 폴더: 현재 위치(currentFolderId)에 만든다. 사이드바 모달 재사용. */
function startCreateFolderHere() {
  sidebar.value?.openCreateModal(currentFolderId.value)
}
</script>

<template>
  <div class="flex h-[calc(100vh-48px)]">
    <HomeSidebar ref="sidebar" @create-project-requested="createModal.open()" />
    <main class="flex-1 p-6 overflow-y-auto">
      <!-- Breadcrumb + Status filter chips + Add menu -->
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2 text-sm text-towa-text-muted">
          <button
            v-if="currentFolder"
            class="p-1 rounded hover:bg-towa-surface hover:text-towa-text transition-colors"
            :title="currentFolder.parentId ? '상위 폴더로' : '루트로'"
            @click="goToParent"
          >
            <ChevronLeft :size="16" />
          </button>
          <span v-if="currentFolder">{{ folderPath }}</span>
          <span v-else>전체</span>
        </div>
        <div class="flex items-center gap-3">
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
          <AddMenu
            variant="toolbar"
            label="추가"
            @create-project="createModal.open()"
            @create-folder="startCreateFolderHere"
          />
        </div>
      </div>

      <ProjectGrid
        :projects="projectsHere"
        :subfolders="subfolders"
        :folder-previews="folderPreviews"
        @select="selectProject"
        @create-project="createModal.open()"
        @create-folder="startCreateFolderHere"
        @open-folder="navigateToFolder"
        @delete-project="confirmDeleteProject"
        @move-project="openMoveModal"
        @drop-on-folder="onDropOnFolder"
        @folder-create-child="onFolderCreateChild"
        @folder-rename="onFolderRename"
        @folder-move="onFolderMove"
        @folder-delete="onFolderDelete"
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

    <MoveToFolderModal
      v-if="projectToMove"
      :open="moveModal.isOpen.value"
      :current-folder-id="projectToMove.folderId ?? null"
      :item-name="projectToMove.name"
      @close="moveModal.close()"
      @submit="submitMove"
    />
  </div>
</template>
