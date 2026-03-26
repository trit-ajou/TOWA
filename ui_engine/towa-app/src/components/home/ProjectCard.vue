<script setup lang="ts">
import { computed } from 'vue'
import type { Project } from '@/types/project'
import { FileText } from 'lucide-vue-next'
import BaseCard from '@/components/common/BaseCard.vue'

const props = defineProps<{
  project: Project
}>()

defineEmits<{
  click: []
}>()

const langLabel = computed(() => {
  const map: Record<string, string> = { ja: 'JA', ko: 'KO', en: 'EN', zh: 'ZH' }
  return `${map[props.project.sourceLang] ?? props.project.sourceLang}→${map[props.project.targetLang] ?? props.project.targetLang}`
})

const statusBadge = computed(() => {
  const map: Record<string, { label: string; bg: string }> = {
    'todo': { label: 'TODO', bg: 'bg-gray-500/80' },
    'in-progress': { label: '진행중', bg: 'bg-towa-accent/80' },
    'done': { label: '완료', bg: 'bg-green-500/80' },
  }
  return map[props.project.status] ?? map.todo
})
</script>

<template>
  <BaseCard hoverable @click="$emit('click')">
    <div class="aspect-[3/4] bg-towa-bg overflow-hidden relative">
      <img
        :src="project.thumbnail"
        :alt="project.name"
        class="w-full h-full object-cover"
      />
      <!-- Overlay badges -->
      <div class="absolute top-1.5 left-1.5 flex items-center gap-1">
        <span class="text-[10px] font-medium text-white px-1.5 py-0.5 rounded" :class="statusBadge.bg">
          {{ statusBadge.label }}
        </span>
      </div>
      <div class="absolute bottom-1.5 left-1.5 right-1.5 flex items-center justify-between">
        <span class="text-[10px] text-white/80 bg-black/40 px-1.5 py-0.5 rounded">{{ langLabel }}</span>
        <span class="text-[10px] text-white/80 bg-black/40 px-1.5 py-0.5 rounded flex items-center gap-0.5">
          <FileText :size="10" />
          {{ project.pageCount }}p
        </span>
      </div>
    </div>
    <div class="px-3 py-2">
      <h3 class="text-sm font-medium text-towa-text truncate">{{ project.name }}</h3>
    </div>
  </BaseCard>
</template>
