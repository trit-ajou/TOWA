<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStore } from 'vuex'
import { Settings, Download, Trash2, MoreHorizontal, User, LogIn, LogOut, Coins } from 'lucide-vue-next'
import { useModal } from '@/composables/useModal'
import { useDeploymentMode } from '@/composables/useDeploymentMode'
import DropdownMenu from './DropdownMenu.vue'
import SettingsModal from './SettingsModal.vue'
import LoginModal from './LoginModal.vue'
import type { ProjectTab } from '@/store/modules/editor'

const route = useRoute()
const router = useRouter()
const store = useStore()
const projectMenu = useModal()
const userMenu = useModal()
const loginModal = useModal()
const { isCloud } = useDeploymentMode()
const isLoggedIn = computed(() => store.getters['auth/isLoggedIn'])
const creditBalance = computed<number>(() => store.state.auth.creditBalance)
const reservedUnits = computed<number>(() => store.state.auth.reservedUnits)

function handleLogout() {
  store.dispatch('auth/logout')
  userMenu.close()
}
const settingsModal = useModal()

const isInProject = computed(() => route.path.startsWith('/project/'))
const isInLibrary = computed(() => route.name === 'library')
const projectId = computed(() => route.params.id as string | undefined)
const project = computed(() => projectId.value ? store.getters['projects/byId'](projectId.value) : null)
const selectedPageId = computed(() => store.getters['editor/selectedPageId'])

// Library folder path (from store)
const libraryPath = computed<string[]>(() => store.getters['library/currentPath'])

const currentTab = computed<ProjectTab>(() => {
  if (route.name === 'editor') return 'edit'
  if (route.name === 'detail-editor') return 'detail'
  return 'home'
})

const tabs = computed(() => [
  { id: 'home' as const, label: '홈', enabled: true },
  { id: 'edit' as const, label: '편집', enabled: !!selectedPageId.value },
  { id: 'detail' as const, label: '상세 편집', enabled: !!selectedPageId.value },
])

// Project folder path segments
const projectFolderSegments = computed(() => {
  if (!project.value?.folder) return []
  return project.value.folder.split('/')
})

function goHome() {
  store.commit('library/SET_PATH', [])
  router.push('/')
}

function goToLibraryPath(path: string[]) {
  store.commit('library/SET_PATH', path)
  if (!isInLibrary.value) router.push('/')
}

function switchTab(tab: ProjectTab) {
  if (!projectId.value) return
  const routes: Record<ProjectTab, string> = {
    home: `/project/${projectId.value}`,
    edit: `/project/${projectId.value}/edit`,
    detail: `/project/${projectId.value}/detail`,
  }
  router.push(routes[tab])
}
</script>

<template>
  <nav class="h-12 bg-towa-surface border-b border-towa-border flex items-center px-4 shrink-0">
    <!-- Left: Logo + path -->
    <div class="flex items-center gap-0 min-w-0 text-sm">
      <!-- Logo (always goes home) -->
      <button
        class="font-bold text-towa-accent tracking-wider shrink-0 hover:text-towa-accent-hover transition-colors px-1 py-1 rounded"
        title="홈"
        @click="goHome"
      >
        TOWA
      </button>

      <!-- Path: always starts with clickable "홈" -->
      <button
        class="text-towa-text-muted hover:text-towa-accent transition-colors cursor-pointer shrink-0 ml-3"
        @click="goHome"
      >
        홈
      </button>

      <!-- Library folder path -->
      <template v-if="isInLibrary && libraryPath.length > 0">
        <template v-for="(seg, i) in libraryPath" :key="i">
          <span class="text-towa-text-muted mx-2 shrink-0 text-xs">&gt;</span>
          <button
            v-if="i < libraryPath.length - 1"
            class="text-towa-text-muted hover:text-towa-accent transition-colors cursor-pointer truncate"
            @click="goToLibraryPath(libraryPath.slice(0, i + 1))"
          >
            {{ seg }}
          </button>
          <span v-else class="font-medium text-towa-text truncate">{{ seg }}</span>
        </template>
      </template>

      <!-- Project path -->
      <template v-if="isInProject && project">
        <template v-for="(seg, i) in projectFolderSegments" :key="i">
          <span class="text-towa-text-muted mx-2 shrink-0 text-xs">&gt;</span>
          <button
            class="text-towa-text-muted hover:text-towa-accent transition-colors cursor-pointer truncate"
            @click="goToLibraryPath(projectFolderSegments.slice(0, i + 1))"
          >
            {{ seg }}
          </button>
        </template>
        <span class="text-towa-text-muted mx-2 shrink-0 text-xs">&gt;</span>
        <span class="font-medium text-towa-text truncate">{{ project.name }}</span>
      </template>
    </div>

    <!-- Center: Tabs (only inside project) -->
    <div v-if="isInProject" class="flex-1 flex justify-center">
      <div class="flex items-center gap-1 bg-towa-bg rounded-lg p-0.5">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="px-3 py-1 text-sm rounded-md transition-colors"
          :class="[
            currentTab === tab.id
              ? 'bg-towa-surface-light text-towa-text font-medium'
              : tab.enabled
                ? 'text-towa-text-muted hover:text-towa-text'
                : 'text-towa-text-muted/40 cursor-not-allowed',
          ]"
          :disabled="!tab.enabled"
          @click="tab.enabled && switchTab(tab.id)"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>
    <div v-else class="flex-1" />

    <!-- Right: credit + project menu + user profile -->
    <div class="flex items-center gap-1">
      <!-- Credit balance (cloud + logged in) -->
      <div
        v-if="isCloud && isLoggedIn"
        class="flex items-center gap-1.5 px-2 py-1 rounded-md bg-towa-bg text-xs mr-1"
        :title="reservedUnits > 0 ? `보유 ${creditBalance} / 예약 ${reservedUnits}` : `크레딧 ${creditBalance}`"
      >
        <Coins :size="14" class="text-towa-accent" />
        <span class="text-towa-text font-mono">{{ creditBalance }}</span>
        <span v-if="reservedUnits > 0" class="text-towa-text-muted font-mono">(-{{ reservedUnits }})</span>
      </div>

      <div v-if="isInProject" class="relative">
        <button
          class="p-1.5 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-text transition-colors"
          @click.stop="projectMenu.toggle()"
        >
          <MoreHorizontal :size="18" />
        </button>
        <DropdownMenu :open="projectMenu.isOpen.value" @close="projectMenu.close()">
          <button class="w-full text-left px-3 py-2 text-sm text-towa-text hover:bg-towa-surface-light flex items-center gap-2 transition-colors">
            <Settings :size="14" />
            프로젝트 설정
          </button>
          <button class="w-full text-left px-3 py-2 text-sm text-towa-text hover:bg-towa-surface-light flex items-center gap-2 transition-colors">
            <Download :size="14" />
            내보내기
          </button>
          <div class="border-t border-towa-border my-1" />
          <button class="w-full text-left px-3 py-2 text-sm text-towa-danger hover:bg-towa-surface-light flex items-center gap-2 transition-colors">
            <Trash2 :size="14" />
            프로젝트 삭제
          </button>
        </DropdownMenu>
      </div>

      <div class="relative">
        <button
          class="p-1.5 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-text transition-colors"
          @click.stop="userMenu.toggle()"
        >
          <User v-if="isCloud" :size="18" />
          <Settings v-else :size="18" />
        </button>
        <DropdownMenu :open="userMenu.isOpen.value" @close="userMenu.close()">
          <!-- Cloud: logged in -->
          <template v-if="isCloud && isLoggedIn">
            <div class="px-3 py-2 border-b border-towa-border">
              <div class="text-sm font-medium text-towa-text">{{ store.state.auth.user?.nickname || '사용자' }}</div>
              <div class="text-xs text-towa-text-muted">{{ store.state.auth.user?.email }}</div>
            </div>
          </template>
          <!-- Cloud: not logged in -->
          <template v-if="isCloud && !isLoggedIn">
            <button
              class="w-full text-left px-3 py-2 text-sm text-towa-text hover:bg-towa-surface-light flex items-center gap-2 transition-colors"
              @click="userMenu.close(); loginModal.open()"
            >
              <LogIn :size="14" />
              로그인
            </button>
          </template>
          <button
            class="w-full text-left px-3 py-2 text-sm text-towa-text hover:bg-towa-surface-light flex items-center gap-2 transition-colors"
            @click="userMenu.close(); settingsModal.open()"
          >
            <Settings :size="14" />
            환경설정
          </button>
          <!-- Cloud: logout -->
          <template v-if="isCloud && isLoggedIn">
            <div class="border-t border-towa-border my-1" />
            <button
              class="w-full text-left px-3 py-2 text-sm text-towa-danger hover:bg-towa-surface-light flex items-center gap-2 transition-colors"
              @click="handleLogout"
            >
              <LogOut :size="14" />
              로그아웃
            </button>
          </template>
        </DropdownMenu>
      </div>
    </div>

    <LoginModal :open="loginModal.isOpen.value" @close="loginModal.close()" @login="loginModal.close()" />

    <SettingsModal :open="settingsModal.isOpen.value" @close="settingsModal.close()" @open-login="loginModal.open()" />
  </nav>
</template>
