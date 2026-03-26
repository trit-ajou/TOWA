<script setup lang="ts">
import { computed } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import { Folder, FolderOpen, ChevronRight, ChevronDown, Clock } from 'lucide-vue-next'
import SearchBar from '@/components/common/SearchBar.vue'
import type { FolderNode } from '@/types/folder'

const store = useStore()
const router = useRouter()

const searchQuery = defineModel<string>('search', { default: '' })
const folderTree = computed<FolderNode[]>(() => store.getters['library/folderTree'])
const currentPath = computed<string[]>(() => store.getters['library/currentPath'])
const recentProjects = computed(() => store.getters['projects/recentlyEdited'](3))

const expanded = defineModel<Set<string>>('expanded', { default: () => new Set<string>() })

function toggleExpand(folderId: string) {
  const next = new Set(expanded.value)
  if (next.has(folderId)) next.delete(folderId)
  else next.add(folderId)
  expanded.value = next
}

function navigateToFolder(path: string[]) {
  store.commit('library/SET_PATH', path)
}

function isActivePath(path: string[]): boolean {
  return JSON.stringify(currentPath.value) === JSON.stringify(path)
}

function openRecentProject(projectId: string) {
  store.commit('editor/SET_CURRENT_PROJECT', projectId)
  store.commit('editor/SET_ACTIVE_TAB', 'home')
  store.commit('editor/SET_SELECTED_PAGE', null)
  router.push(`/project/${projectId}`)
}

</script>

<template>
  <aside class="w-60 bg-towa-surface border-r border-towa-border p-4 flex flex-col shrink-0 overflow-y-auto">
    <!-- Search -->
    <SearchBar v-model="searchQuery" placeholder="프로젝트 검색..." />

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

    <!-- Folder tree (no section header, just the tree) -->
    <div>
      <!-- Root = 전체 -->
      <button
        class="w-full text-left text-sm px-2.5 py-1.5 rounded transition-colors flex items-center gap-1.5 mb-0.5"
        :class="currentPath.length === 0
          ? 'bg-towa-accent/15 text-towa-accent'
          : 'text-towa-text-muted hover:text-towa-text hover:bg-towa-surface-light'"
        @click="navigateToFolder([])"
      >
        <FolderOpen v-if="currentPath.length === 0" :size="14" />
        <Folder v-else :size="14" />
        전체
      </button>

      <!-- Level 1 -->
      <div v-for="folder in folderTree" :key="folder.id" class="ml-2">
        <div class="flex items-center">
          <button
            v-if="folder.children.length > 0"
            class="p-0.5 text-towa-text-muted hover:text-towa-text shrink-0"
            @click="toggleExpand(folder.id)"
          >
            <ChevronDown v-if="expanded.has(folder.id)" :size="12" />
            <ChevronRight v-else :size="12" />
          </button>
          <span v-else class="w-4" />
          <button
            class="flex-1 text-left text-sm px-2 py-1.5 rounded transition-colors flex items-center gap-1.5"
            :class="isActivePath([folder.name])
              ? 'bg-towa-accent/15 text-towa-accent'
              : 'text-towa-text-muted hover:text-towa-text hover:bg-towa-surface-light'"
            @click="navigateToFolder([folder.name])"
          >
            <FolderOpen v-if="isActivePath([folder.name])" :size="14" />
            <Folder v-else :size="14" />
            {{ folder.name }}
          </button>
        </div>

        <!-- Level 2 -->
        <div v-if="expanded.has(folder.id) && folder.children.length > 0" class="ml-5">
          <button
            v-for="sub in folder.children"
            :key="sub.id"
            class="w-full text-left text-sm px-2 py-1 rounded transition-colors flex items-center gap-1.5"
            :class="isActivePath([folder.name, sub.name])
              ? 'bg-towa-accent/15 text-towa-accent'
              : 'text-towa-text-muted hover:text-towa-text hover:bg-towa-surface-light'"
            @click="navigateToFolder([folder.name, sub.name])"
          >
            <Folder :size="12" />
            {{ sub.name }}
          </button>
        </div>
      </div>
    </div>

    <!-- Status filter moved to main content area -->
  </aside>
</template>
