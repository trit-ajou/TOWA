<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import { Folder as FolderIcon, FolderOpen, Clock, Trash2, FolderPlus } from 'lucide-vue-next'
import SearchBar from '@/components/common/SearchBar.vue'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import FolderTreeNode from '@/components/home/FolderTreeNode.vue'
import MoveToFolderModal from '@/components/home/MoveToFolderModal.vue'
import { useModal } from '@/composables/useModal'
import type { Folder, FolderNode } from '@/types/folder'
import type { Project } from '@/types/project'
import { validateFolderNameSyntax, MAX_FOLDER_DEPTH } from '@/types/folder'

const store = useStore()
const router = useRouter()

const searchInput = ref<string>(store.getters['library/searchQuery'] ?? '')
function syncSearch(v: string) {
  searchInput.value = v
  store.commit('library/SET_SEARCH_QUERY', v)
}

const tree = computed<FolderNode[]>(() => store.getters['folders/tree'])
const childrenOf = computed(() => store.getters['folders/childrenOf'] as (parentId: string | null) => Array<{ id: string; name: string }>)
const currentFolderId = computed<string | null>(() => store.getters['library/currentFolderId'])
const recentProjects = computed(() => store.getters['projects/recentlyEdited'](3))

const expanded = ref<Set<string>>(new Set())
function toggleExpand(folderId: string) {
  const next = new Set(expanded.value)
  if (next.has(folderId)) next.delete(folderId)
  else next.add(folderId)
  expanded.value = next
}

function navigateToFolder(folderId: string | null) {
  store.commit('library/SET_CURRENT_FOLDER', folderId)
}

function openRecentProject(projectId: string) {
  store.commit('editor/SET_CURRENT_PROJECT', projectId)
  store.commit('editor/SET_ACTIVE_TAB', 'home')
  store.commit('editor/SET_SELECTED_PAGE', null)
  router.push(`/project/${projectId}`)
}

// --- Folder action menu ---

const menuFolderId = ref<string | null>(null)
function openMenu(id: string, ev: Event) {
  ev.stopPropagation()
  menuFolderId.value = menuFolderId.value === id ? null : id
}
function closeMenu() { menuFolderId.value = null }

// --- Create folder modal ---

const createModal = useModal()
const createParentId = ref<string | null>(null)
const newFolderName = ref('')
const createError = ref<string | null>(null)

function openCreateModal(parentId: string | null) {
  createParentId.value = parentId
  newFolderName.value = ''
  createError.value = null
  closeMenu()
  createModal.open()
}

function validateNameForCreate(name: string, parentId: string | null): string | null {
  const syntaxErr = validateFolderNameSyntax(name)
  if (syntaxErr === 'empty') return '이름을 입력해주세요.'
  if (syntaxErr === 'too-long') return '폴더 이름이 너무 깁니다 (100자 이내).'
  if (syntaxErr === 'forbidden-char') return '슬래시 / 백슬래시 등은 사용할 수 없습니다.'
  const siblings = childrenOf.value(parentId)
  if (siblings.some((f) => f.name.trim().toLowerCase() === name.trim().toLowerCase())) {
    return '같은 위치에 동일한 이름의 폴더가 이미 있습니다.'
  }
  if ((store.getters['folders/wouldExceedMaxDepth'] as (p: string | null) => boolean)(parentId)) {
    return `폴더 깊이는 최대 ${MAX_FOLDER_DEPTH}단계까지 가능합니다.`
  }
  return null
}

async function submitCreateFolder() {
  const err = validateNameForCreate(newFolderName.value, createParentId.value)
  if (err) { createError.value = err; return }
  try {
    await store.dispatch('folders/create', { name: newFolderName.value.trim(), parentId: createParentId.value })
    createModal.close()
  } catch (e) {
    createError.value = e instanceof Error ? e.message : '폴더 생성 실패'
  }
}

// --- Rename modal ---

const renameModal = useModal()
const renameTargetId = ref<string | null>(null)
const renameInput = ref('')
const renameError = ref<string | null>(null)

function openRenameModal(folderId: string) {
  const f = store.getters['folders/byId'](folderId)
  if (!f) return
  renameTargetId.value = folderId
  renameInput.value = f.name
  renameError.value = null
  closeMenu()
  renameModal.open()
}

async function submitRename() {
  if (!renameTargetId.value) return
  const f = store.getters['folders/byId'](renameTargetId.value)
  if (!f) return
  const err = validateNameForCreate(renameInput.value, f.parentId)
  // 자기 자신과 같은 이름이면 OK
  if (err && renameInput.value.trim().toLowerCase() !== f.name.toLowerCase()) {
    renameError.value = err; return
  }
  try {
    await store.dispatch('folders/rename', { id: renameTargetId.value, name: renameInput.value.trim() })
    renameModal.close()
  } catch (e) {
    renameError.value = e instanceof Error ? e.message : '이름 변경 실패'
  }
}

// --- Delete dialog (3-option) ---

const deleteModal = useModal()
const deleteTargetId = ref<string | null>(null)
const deleteError = ref<string | null>(null)
const deleteTarget = computed(() => deleteTargetId.value ? store.getters['folders/byId'](deleteTargetId.value) : null)
const deleteHasChildren = computed(() => {
  if (!deleteTargetId.value) return false
  const childFolders = childrenOf.value(deleteTargetId.value).length
  const childProjects = (store.getters['projects/all'] as { folderId: string | null }[]).filter((p) => p.folderId === deleteTargetId.value).length
  return (childFolders + childProjects) > 0
})
const deleteChildCount = computed(() => {
  if (!deleteTargetId.value) return 0
  const childFolders = (store.getters['folders/descendantIds'] as (id: string) => string[])(deleteTargetId.value).length
  const childProjects = (store.getters['projects/all'] as { folderId: string | null }[]).filter((p) => {
    const descSet = new Set([deleteTargetId.value!, ...(store.getters['folders/descendantIds'] as (id: string) => string[])(deleteTargetId.value!)])
    return p.folderId && descSet.has(p.folderId)
  }).length
  return childFolders + childProjects
})
const deleteParentName = computed(() => {
  const f = deleteTarget.value
  if (!f) return '루트'
  if (!f.parentId) return '루트'
  return store.getters['folders/byId'](f.parentId)?.name ?? '루트'
})

function openDeleteDialog(folderId: string) {
  deleteTargetId.value = folderId
  deleteError.value = null
  closeMenu()
  deleteModal.open()
}

async function deleteFolder(mode: 'empty' | 'cascade-trash' | 'reparent') {
  if (!deleteTargetId.value) return
  try {
    await store.dispatch('folders/remove', { id: deleteTargetId.value, mode })
    // 만약 현재 폴더가 삭제됐다면 루트로 이동
    if (currentFolderId.value === deleteTargetId.value) {
      store.commit('library/SET_CURRENT_FOLDER', null)
    }
    deleteModal.close()
  } catch (e) {
    deleteError.value = e instanceof Error ? e.message : '삭제 실패'
  }
}

function goToTrash() {
  router.push('/trash')
}

// --- Move folder modal ---

const moveModal = useModal()
const moveTargetId = ref<string | null>(null)
const moveTarget = computed<Folder | null>(() =>
  moveTargetId.value ? (store.getters['folders/byId'](moveTargetId.value) as Folder | undefined) ?? null : null,
)
const moveDisabledIds = computed<Set<string>>(() => {
  if (!moveTargetId.value) return new Set()
  const descIds = (store.getters['folders/descendantIds'] as (id: string) => string[])(moveTargetId.value)
  return new Set([moveTargetId.value, ...descIds])
})

function openMoveFolderModal(folderId: string) {
  moveTargetId.value = folderId
  closeMenu()
  moveModal.open()
}

async function submitMoveFolder(parentId: string | null) {
  if (!moveTargetId.value) return
  try {
    await store.dispatch('folders/move', { id: moveTargetId.value, parentId })
    moveModal.close()
    moveTargetId.value = null
  } catch (e) {
    console.warn('[folders/move]', e)
  }
}

// --- Drag & drop handlers (project → folder) ---

async function moveProjectTo(folderId: string | null, projectId: string) {
  const project = store.getters['projects/byId'](projectId) as Project | undefined
  if (!project) return
  if ((project.folderId ?? null) === folderId) return
  try {
    await store.dispatch('projects/update', { ...project, folderId })
  } catch (e) {
    console.warn('[projects/update folder]', e)
  }
}

function onRootDragOver(ev: DragEvent) {
  if (!ev.dataTransfer) return
  if (Array.from(ev.dataTransfer.types).includes('application/x-towa-project-id')) {
    ev.dataTransfer.dropEffect = 'move'
  }
}
function onRootDrop(ev: DragEvent) {
  const id = ev.dataTransfer?.getData('application/x-towa-project-id')
  if (!id) return
  moveProjectTo(null, id)
}

defineExpose({
  openCreateModal,
  openRenameModal,
  openDeleteDialog,
  openMoveFolderModal,
})
</script>

<template>
  <aside class="w-60 bg-towa-surface border-r border-towa-border p-4 flex flex-col shrink-0 overflow-y-auto" @click.self="closeMenu">
    <!-- Search -->
    <SearchBar :model-value="searchInput" @update:model-value="syncSearch" placeholder="프로젝트 검색..." />

    <div class="border-b border-towa-border my-3" />

    <!-- Recent projects -->
    <div>
      <h3 class="text-xs font-semibold text-towa-text-muted uppercase tracking-wider mb-2 flex items-center gap-1.5">
        <Clock :size="14" />
        최근 프로젝트
      </h3>
      <ul class="space-y-0.5">
        <li v-for="proj in recentProjects" :key="proj.id">
          <button
            class="w-full text-left px-2.5 py-1.5 rounded hover:bg-towa-surface-light transition-colors group"
            @click="openRecentProject(proj.id)"
          >
            <div class="text-sm text-towa-text truncate group-hover:text-towa-accent transition-colors">{{ proj.name }}</div>
            <div class="text-[10px] text-towa-text-muted">{{ new Date(proj.updatedAt).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) }}</div>
          </button>
        </li>
      </ul>
    </div>

    <div class="border-b border-towa-border my-3" />

    <!-- Folder tree -->
    <div>
      <div class="flex items-center justify-between mb-1">
        <h3 class="text-xs font-semibold text-towa-text-muted uppercase tracking-wider">폴더</h3>
        <button
          class="p-1 text-towa-text-muted hover:text-towa-accent rounded transition-colors"
          title="새 폴더 (루트)"
          @click="openCreateModal(null)"
        >
          <FolderPlus :size="14" />
        </button>
      </div>

      <!-- Root (drop target for moving to root) -->
      <button
        class="w-full text-left text-sm px-2.5 py-1.5 rounded transition-colors flex items-center gap-1.5 mb-0.5"
        :class="currentFolderId === null
          ? 'bg-towa-accent/15 text-towa-accent'
          : 'text-towa-text-muted hover:text-towa-text hover:bg-towa-surface-light'"
        @click="navigateToFolder(null)"
        @dragover.prevent="onRootDragOver"
        @drop.prevent="onRootDrop"
      >
        <FolderOpen v-if="currentFolderId === null" :size="14" />
        <FolderIcon v-else :size="14" />
        전체
      </button>

      <!-- Tree -->
      <template v-for="folder in tree" :key="folder.id">
        <FolderTreeNode
          :folder="folder"
          :expanded="expanded"
          :current-folder-id="currentFolderId"
          :menu-folder-id="menuFolderId"
          :level="0"
          @toggle="toggleExpand"
          @navigate="navigateToFolder"
          @open-menu="openMenu"
          @create-child="openCreateModal"
          @rename="openRenameModal"
          @delete="openDeleteDialog"
          @move="openMoveFolderModal"
          @drop-project="moveProjectTo"
        />
      </template>
    </div>

    <div class="border-b border-towa-border my-3" />

    <!-- Trash -->
    <button
      class="text-left text-sm px-2.5 py-1.5 rounded text-towa-text-muted hover:text-towa-text hover:bg-towa-surface-light transition-colors flex items-center gap-1.5"
      @click="goToTrash"
    >
      <Trash2 :size="14" />
      휴지통
    </button>

    <!-- Create folder modal -->
    <BaseModal :open="createModal.isOpen.value" title="새 폴더" @close="createModal.close()">
      <div class="space-y-2">
        <input
          v-model="newFolderName"
          class="w-full px-3 py-2 bg-towa-surface-light border border-towa-border rounded text-sm focus:outline-none focus:border-towa-accent"
          placeholder="폴더 이름"
          @keydown.enter="submitCreateFolder"
          ref="el => el && el.focus()"
        />
        <p v-if="createError" class="text-xs text-red-400">{{ createError }}</p>
      </div>
      <template #footer>
        <BaseButton variant="secondary" size="sm" @click="createModal.close()">취소</BaseButton>
        <BaseButton variant="primary" size="sm" @click="submitCreateFolder">만들기</BaseButton>
      </template>
    </BaseModal>

    <!-- Rename modal -->
    <BaseModal :open="renameModal.isOpen.value" title="폴더 이름 변경" @close="renameModal.close()">
      <div class="space-y-2">
        <input
          v-model="renameInput"
          class="w-full px-3 py-2 bg-towa-surface-light border border-towa-border rounded text-sm focus:outline-none focus:border-towa-accent"
          @keydown.enter="submitRename"
        />
        <p v-if="renameError" class="text-xs text-red-400">{{ renameError }}</p>
      </div>
      <template #footer>
        <BaseButton variant="secondary" size="sm" @click="renameModal.close()">취소</BaseButton>
        <BaseButton variant="primary" size="sm" @click="submitRename">변경</BaseButton>
      </template>
    </BaseModal>

    <!-- Move folder modal -->
    <MoveToFolderModal
      v-if="moveTarget"
      :open="moveModal.isOpen.value"
      :current-folder-id="moveTarget.parentId"
      :item-name="moveTarget.name"
      :disabled-ids="moveDisabledIds"
      @close="moveModal.close()"
      @submit="submitMoveFolder"
    />

    <!-- Delete dialog -->
    <BaseModal :open="deleteModal.isOpen.value" title="폴더 삭제" @close="deleteModal.close()">
      <div class="space-y-3 text-sm">
        <p v-if="!deleteHasChildren" class="text-towa-text-muted">
          <span class="font-medium text-towa-text">{{ deleteTarget?.name }}</span>
          폴더를 휴지통으로 옮깁니다.
        </p>
        <template v-else>
          <p class="text-towa-text-muted">
            <span class="font-medium text-towa-text">{{ deleteTarget?.name }}</span>
            폴더에 항목 {{ deleteChildCount }}개가 있습니다.
          </p>
          <p class="text-xs text-towa-text-muted">어떻게 할지 선택해주세요.</p>
        </template>
        <p v-if="deleteError" class="text-xs text-red-400">{{ deleteError }}</p>
      </div>
      <template #footer>
        <BaseButton variant="secondary" size="sm" @click="deleteModal.close()">취소</BaseButton>
        <template v-if="!deleteHasChildren">
          <BaseButton variant="danger" size="sm" @click="deleteFolder('empty')">삭제</BaseButton>
        </template>
        <template v-else>
          <BaseButton variant="secondary" size="sm" @click="deleteFolder('reparent')">
            {{ deleteParentName }} 폴더로 이동
          </BaseButton>
          <BaseButton variant="danger" size="sm" @click="deleteFolder('cascade-trash')">
            {{ deleteChildCount }}개 항목 휴지통으로
          </BaseButton>
        </template>
      </template>
    </BaseModal>
  </aside>
</template>
