<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Project } from '@/types/project'
import type { Page } from '@/types/page'
import { ChevronRight, Edit3, Paintbrush } from 'lucide-vue-next'

const props = defineProps<{
  project: Project
  pages: Page[]
  lastPageId: string | null
  lastEditMode: 'edit' | 'detail'
}>()

const emit = defineEmits<{
  resume: [mode: 'edit' | 'detail']
}>()

const modeMenuOpen = ref(false)
const triggerBtn = ref<HTMLElement>()
const menuStyle = ref({ top: '0px', left: '0px' })

function toggleMenu() {
  if (modeMenuOpen.value) {
    modeMenuOpen.value = false
    return
  }
  if (triggerBtn.value) {
    const rect = triggerBtn.value.getBoundingClientRect()
    menuStyle.value = {
      top: `${rect.top}px`,
      left: `${rect.right + 4}px`,
    }
  }
  modeMenuOpen.value = true
}

const lastPage = computed(() => {
  if (props.lastPageId) {
    return props.pages.find((p) => p.id === props.lastPageId)
  }
  return props.pages[0] ?? null
})

const completedCount = computed(() =>
  props.pages.filter((p) => p.status === 'done').length
)

const progressPercent = computed(() =>
  props.pages.length > 0 ? Math.round((completedCount.value / props.pages.length) * 100) : 0
)

const langLabel = computed(() => {
  const map: Record<string, string> = { ja: '日本語', ko: '한국어', en: 'English', zh: '中文' }
  return `${map[props.project.sourceLang] ?? props.project.sourceLang} → ${map[props.project.targetLang] ?? props.project.targetLang}`
})

const resumeLabel = computed(() => {
  const modeLabel = props.lastEditMode === 'detail' ? '이어서 상세 편집' : '이어서 편집'
  const pageLabel = lastPage.value ? ` : ${lastPage.value.index}p` : ''
  return `${modeLabel}${pageLabel}`
})

function onResume() {
  emit('resume', props.lastEditMode)
}

function onResumeMode(mode: 'edit' | 'detail') {
  modeMenuOpen.value = false
  emit('resume', mode)
}
</script>

<template>
  <div class="bg-towa-surface border border-towa-border rounded-lg overflow-hidden p-4 flex flex-col gap-3">
    <!-- Thumbnail -->
    <div v-if="lastPage" class="w-full rounded-md overflow-hidden border border-towa-border">
      <img
        :src="lastPage.thumbnail"
        :alt="`${lastPage.index}p`"
        class="w-full aspect-[2/3] object-cover"
      />
    </div>

    <!-- Title -->
    <h2 class="text-base font-semibold text-towa-text truncate">{{ project.name }}</h2>

    <!-- Meta: lang left, pages right -->
    <div class="flex items-center justify-between text-xs text-towa-text-muted">
      <span>{{ langLabel }}</span>
      <span>{{ project.pageCount }}p</span>
    </div>

    <!-- Progress bar -->
    <div>
      <div class="flex items-center justify-between text-xs mb-1">
        <span class="text-towa-text-muted">{{ completedCount }} / {{ pages.length }} 완료</span>
        <span class="text-towa-accent font-medium">{{ progressPercent }}%</span>
      </div>
      <div class="h-1.5 bg-towa-bg rounded-full overflow-hidden">
        <div
          class="h-full bg-towa-accent rounded-full transition-all"
          :style="{ width: `${progressPercent}%` }"
        />
      </div>
    </div>

    <!-- Resume button with mode dropdown -->
    <div ref="btnContainer" class="mt-1">
      <div class="flex">
        <button
          class="flex-1 flex items-center justify-center gap-2 bg-towa-accent hover:bg-towa-accent-hover text-white text-base font-medium py-3 px-4 rounded-l-md transition-colors"
          @click="onResume"
        >
          {{ resumeLabel }}
        </button>
        <button
          ref="triggerBtn"
          class="bg-towa-accent hover:bg-towa-accent-hover text-white px-3 py-3 rounded-r-md border-l border-white/20 transition-colors"
          @click.stop="toggleMenu"
        >
          <ChevronRight :size="14" />
        </button>
      </div>

      <!-- Mode dropdown (teleported to body, positioned next to button) -->
      <Teleport to="body">
        <div
          v-if="modeMenuOpen"
          class="fixed z-50"
          :style="menuStyle"
        >
          <div class="w-44 bg-towa-surface border border-towa-border rounded-md shadow-xl py-1">
            <button
              class="w-full text-left px-3 py-2 text-sm hover:bg-towa-surface-light flex items-center gap-2 transition-colors"
              :class="lastEditMode === 'edit' ? 'text-towa-accent' : 'text-towa-text'"
              @click="onResumeMode('edit')"
            >
              <Edit3 :size="14" />
              편집 모드
            </button>
            <button
              class="w-full text-left px-3 py-2 text-sm hover:bg-towa-surface-light flex items-center gap-2 transition-colors"
              :class="lastEditMode === 'detail' ? 'text-towa-accent' : 'text-towa-text'"
              @click="onResumeMode('detail')"
            >
              <Paintbrush :size="14" />
              상세 편집 모드
            </button>
          </div>
          <div class="fixed inset-0 -z-10" @click="modeMenuOpen = false" />
        </div>
      </Teleport>
    </div>
  </div>
</template>
