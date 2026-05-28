<script setup lang="ts">
import { computed } from 'vue'
import type { Project } from '@/types/project'
import { FileText, Trash2, FolderInput } from 'lucide-vue-next'
import BaseCard from '@/components/common/BaseCard.vue'

const props = defineProps<{
  project: Project
}>()

const emit = defineEmits<{
  click: []
  delete: []
  move: []
  /** Drag started on this project card. Payload: projectId. */
  dragStart: [projectId: string]
}>()

function onDragStart(ev: DragEvent) {
  if (!ev.dataTransfer) return
  ev.dataTransfer.effectAllowed = 'move'
  ev.dataTransfer.setData('application/x-towa-project-id', props.project.id)

  // Compact drag ghost: small thumbnail + name pill
  const ghost = document.createElement('div')
  ghost.style.cssText = [
    'position: fixed',
    'top: -1000px',
    'left: -1000px',
    'width: 120px',
    'display: flex',
    'align-items: center',
    'gap: 8px',
    'padding: 6px 10px 6px 6px',
    'background: rgba(30, 30, 50, 0.95)',
    'color: white',
    'border: 1px solid rgba(255,255,255,0.15)',
    'border-radius: 6px',
    'box-shadow: 0 8px 24px rgba(0,0,0,0.4)',
    'font-size: 12px',
    'font-family: inherit',
    'pointer-events: none',
  ].join(';')
  if (props.project.thumbnail) {
    const img = document.createElement('img')
    img.src = props.project.thumbnail
    img.style.cssText = 'width: 24px; height: 32px; object-fit: cover; border-radius: 3px; flex-shrink: 0'
    ghost.appendChild(img)
  }
  const label = document.createElement('span')
  label.textContent = props.project.name
  label.style.cssText = 'overflow: hidden; text-overflow: ellipsis; white-space: nowrap'
  ghost.appendChild(label)

  document.body.appendChild(ghost)
  ev.dataTransfer.setDragImage(ghost, 12, 18)
  // Removed on next tick (after the browser snapshots it for the drag image)
  setTimeout(() => ghost.remove(), 0)

  emit('dragStart', props.project.id)
}

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
  <BaseCard class="group" hoverable :draggable="true" @click="$emit('click')" @dragstart="onDragStart">
    <div class="aspect-[3/4] bg-towa-bg overflow-hidden relative">
      <img
        v-if="project.thumbnail"
        :src="project.thumbnail"
        :alt="project.name"
        class="w-full h-full object-cover pointer-events-none"
      />
      <div v-else class="w-full h-full flex items-center justify-center text-towa-text-muted text-xs px-2 text-center pointer-events-none">
        {{ project.name }}
      </div>
      <!-- Action buttons on hover -->
      <div class="absolute top-1.5 right-1.5 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          class="p-1 rounded-md bg-black/60 text-white/80 hover:bg-towa-accent hover:text-white transition-colors"
          @click.stop="emit('move')"
          title="다른 폴더로 이동"
        >
          <FolderInput :size="14" />
        </button>
        <button
          class="p-1 rounded-md bg-black/60 text-white/80 hover:bg-red-600 hover:text-white transition-colors"
          @click.stop="emit('delete')"
          title="프로젝트 삭제"
        >
          <Trash2 :size="14" />
        </button>
      </div>
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
