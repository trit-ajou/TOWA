<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStore } from 'vuex'
import { useRoute, useRouter } from 'vue-router'
import type { EditMode } from '@/store/modules/editor'
import type { PageStatus } from '@/types/page'
import ProjectDashboard from '@/components/project/ProjectDashboard.vue'
import PageGrid from '@/components/project/PageGrid.vue'

defineOptions({ name: 'ProjectHomeTab' })

const store = useStore()
const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.params.id as string)
const project = computed(() => store.getters['projects/byId'](projectId.value))
const allPages = computed(() => store.getters['pages/forProject'](projectId.value))
const selectedPageId = computed(() => store.getters['editor/selectedPageId'])
const lastEditMode = computed<EditMode>(() => store.getters['editor/lastEditMode'])
const layout = computed(() => store.getters['editor/projectHomeLayout'])

const statusFilter = ref<PageStatus | 'all'>('all')

const statusChips = [
  { value: 'all' as const, label: '전체' },
  { value: 'waiting' as const, label: '대기' },
  { value: 'ai-processing' as const, label: 'AI 처리중' },
  { value: 'in-progress' as const, label: '작업중' },
  { value: 'done' as const, label: '완료' },
]

const filteredPages = computed(() => {
  if (statusFilter.value === 'all') return allPages.value
  return allPages.value.filter((p: { status: PageStatus }) => p.status === statusFilter.value)
})

function resume(mode: EditMode) {
  const pageId = selectedPageId.value ?? allPages.value[0]?.id
  if (!pageId) return
  store.commit('editor/SET_SELECTED_PAGE', pageId)
  const r = mode === 'detail' ? 'detail' : 'edit'
  router.push(`/project/${projectId.value}/${r}`)
}

function selectAndEdit(pageId: string) {
  store.commit('editor/SET_SELECTED_PAGE', pageId)
  router.push(`/project/${projectId.value}/edit`)
}

function selectAndDetail(pageId: string) {
  store.commit('editor/SET_SELECTED_PAGE', pageId)
  router.push(`/project/${projectId.value}/detail`)
}
</script>

<template>
  <main class="h-full flex overflow-hidden">
    <!-- Vertical -->
    <template v-if="layout === 'vertical'">
      <div class="flex-1 flex flex-col min-h-0">
        <div class="shrink-0 px-6 pt-4 pb-3">
          <ProjectDashboard
            v-if="project"
            :project="project"
            :pages="allPages"
            :last-page-id="selectedPageId"
            :last-edit-mode="lastEditMode"
            @resume="resume"
          />
        </div>
        <div class="flex-1 overflow-y-auto px-6 pb-6">
          <!-- Status filter chips -->
          <div class="flex items-center justify-end mb-3">
            <div class="flex items-center gap-1 bg-towa-surface rounded-lg p-0.5">
              <button
                v-for="chip in statusChips"
                :key="chip.value"
                class="px-2.5 py-1 text-xs rounded-md transition-colors"
                :class="statusFilter === chip.value
                  ? 'bg-towa-surface-light text-towa-text font-medium'
                  : 'text-towa-text-muted hover:text-towa-text'"
                @click="statusFilter = chip.value"
              >
                {{ chip.label }}
              </button>
            </div>
          </div>
          <PageGrid
            :pages="filteredPages"
            :selected-page-id="selectedPageId"
            @open-edit="selectAndEdit"
            @open-detail="selectAndDetail"
          />
        </div>
      </div>
    </template>

    <!-- Horizontal -->
    <template v-else>
      <div class="w-[280px] shrink-0 p-5 overflow-y-auto">
        <ProjectDashboard
          v-if="project"
          :project="project"
          :pages="allPages"
          :last-page-id="selectedPageId"
          :last-edit-mode="lastEditMode"
          @resume="resume"
        />
      </div>
      <div class="flex-1 overflow-y-auto p-5">
        <!-- Status filter chips -->
        <div class="flex items-center justify-end mb-3">
          <div class="flex items-center gap-1 bg-towa-surface rounded-lg p-0.5">
            <button
              v-for="chip in statusChips"
              :key="chip.value"
              class="px-2.5 py-1 text-xs rounded-md transition-colors"
              :class="statusFilter === chip.value
                ? 'bg-towa-surface-light text-towa-text font-medium'
                : 'text-towa-text-muted hover:text-towa-text'"
              @click="statusFilter = chip.value"
            >
              {{ chip.label }}
            </button>
          </div>
        </div>
        <PageGrid
          :pages="filteredPages"
          :selected-page-id="selectedPageId"
          @open-edit="selectAndEdit"
          @open-detail="selectAndDetail"
        />
      </div>
    </template>
  </main>
</template>
