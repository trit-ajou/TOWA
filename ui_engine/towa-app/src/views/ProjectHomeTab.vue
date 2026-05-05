<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStore } from 'vuex'
import { useRoute, useRouter } from 'vue-router'
import type { EditMode } from '@/store/modules/editor'
import type { PageStatus } from '@/types/page'
import type { PageSnapshot } from '@/file-adapter'
import { createUlid } from '@/utils/ulid'
import { useModal } from '@/composables/useModal'
import ProjectDashboard from '@/components/project/ProjectDashboard.vue'
import PageGrid from '@/components/project/PageGrid.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import BaseButton from '@/components/common/BaseButton.vue'
// @ts-expect-error bitmappery JS module
import DocumentFactory from '@bitmappery/factories/document-factory'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'

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

const deleteModal = useModal()
const pageToDeleteId = ref<string | null>(null)

const pageToDeleteIndex = computed(() => {
  if (!pageToDeleteId.value) return null
  const page = allPages.value.find((p: { id: string }) => p.id === pageToDeleteId.value)
  return page?.index ?? null
})

function confirmDeletePage(pageId: string) {
  pageToDeleteId.value = pageId
  deleteModal.open()
}

async function deletePage() {
  if (!pageToDeleteId.value) return
  const pid = projectId.value
  await store.dispatch('pages/removePage', { projectId: pid, pageId: pageToDeleteId.value })

  const proj = project.value
  if (proj) {
    await store.dispatch('projects/update', {
      ...proj,
      pageCount: allPages.value.length,
      updatedAt: new Date().toISOString(),
    })
  }

  if (selectedPageId.value === pageToDeleteId.value) {
    store.commit('editor/SET_SELECTED_PAGE', null)
  }

  deleteModal.close()
  pageToDeleteId.value = null
}

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

/**
 * 이미지 파일로 썸네일 Blob 생성 (Canvas 축소)
 */
function generateThumbnail(file: File, maxW = 200, maxH = 300): Promise<Blob> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => {
      const scale = Math.min(maxW / img.width, maxH / img.height, 1)
      const w = Math.round(img.width * scale)
      const h = Math.round(img.height * scale)
      const canvas = document.createElement('canvas')
      canvas.width = w
      canvas.height = h
      const ctx = canvas.getContext('2d')!
      ctx.drawImage(img, 0, 0, w, h)
      canvas.toBlob((blob) => resolve(blob!), 'image/png')
      URL.revokeObjectURL(img.src)
    }
    img.src = URL.createObjectURL(file)
  })
}

async function addPages(files: File[]) {
  const pid = projectId.value

  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    const currentCount = allPages.value.length
    const pageIndex = currentCount + 1
    const pageId = createUlid()

    // 원본 이미지 blob
    const originalImage = file as Blob

    // 썸네일 생성
    const thumbnail = await generateThumbnail(file)

    // bitmappery document 생성 → layerBlob
    const imgCanvas = await blobToCanvas(file)
    const doc = DocumentFactory.create({
      name: `page-${pageId}`,
      width: imgCanvas.width,
      height: imgCanvas.height,
      layers: [
        LayerFactory.create({
          name: 'original',
          source: imgCanvas,
          width: imgCanvas.width,
          height: imgCanvas.height,
        }),
      ],
    })
    const layerBlob = await DocumentFactory.toBlob(doc) as Blob

    const snapshot: PageSnapshot = {
      page: {
        id: pageId,
        projectId: pid,
        index: pageIndex,
        status: 'waiting',
        textBlocks: [],
      },
      originalImage,
      layerBlob,
      thumbnail,
    }

    // createPage (snapshot) → IndexedDB + Vuex
    await store.dispatch('pages/addPage', { projectId: pid, snapshot })
  }

  // 프로젝트 pageCount/updatedAt 갱신 (createPage가 이미 갱신하지만 Vuex도 동기화)
  const proj = project.value
  if (proj) {
    await store.dispatch('projects/update', {
      ...proj,
      pageCount: allPages.value.length,
      updatedAt: new Date().toISOString(),
    })
  }
}

function blobToCanvas(blob: Blob): Promise<HTMLCanvasElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d')!
      ctx.drawImage(img, 0, 0)
      URL.revokeObjectURL(img.src)
      resolve(canvas)
    }
    img.onerror = reject
    img.src = URL.createObjectURL(blob)
  })
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
            :project-id="projectId"
            @open-edit="selectAndEdit"
            @open-detail="selectAndDetail"
            @add-pages="addPages"
            @delete-page="confirmDeletePage"
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
          :project-id="projectId"
          @open-edit="selectAndEdit"
          @open-detail="selectAndDetail"
          @add-pages="addPages"
          @delete-page="confirmDeletePage"
        />
      </div>
    </template>
  </main>

  <BaseModal
    title="페이지 삭제"
    :open="deleteModal.isOpen.value"
    @close="deleteModal.close()"
  >
    <p class="text-sm text-towa-text-muted">
      <span class="font-medium text-towa-text">{{ pageToDeleteIndex }}페이지</span>를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.
    </p>
    <template #footer>
      <BaseButton variant="secondary" size="sm" @click="deleteModal.close()">취소</BaseButton>
      <BaseButton variant="danger" size="sm" @click="deletePage">삭제</BaseButton>
    </template>
  </BaseModal>
</template>
