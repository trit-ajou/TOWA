<script setup lang="ts">
import { ref } from 'vue'
import type { Page } from '@/types/page'
import { Plus, Wand2 } from 'lucide-vue-next'
import BaseButton from '@/components/common/BaseButton.vue'
import PageThumbnail from './PageThumbnail.vue'

const props = defineProps<{
  pages: Page[]
  selectedPageId: string | null
  projectId: string
}>()

const emit = defineEmits<{
  openEdit: [pageId: string]
  openDetail: [pageId: string]
  addPages: [files: File[]]
  deletePage: [pageId: string]
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const isDragging = ref(false)

function openFilePicker() {
  fileInput.value?.click()
}

function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) {
    emit('addPages', Array.from(input.files))
    input.value = ''
  }
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const files = Array.from(e.dataTransfer?.files ?? []).filter(f => f.type.startsWith('image/'))
  if (files.length) {
    emit('addPages', files)
  }
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function onDragLeave() {
  isDragging.value = false
}
</script>

<template>
  <div
    @drop.prevent="onDrop"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
  >
    <input
      ref="fileInput"
      type="file"
      accept="image/*"
      multiple
      class="hidden"
      @change="onFileSelect"
    />
    <div class="flex items-center gap-2 mb-4">
      <BaseButton variant="secondary" size="sm" @click="openFilePicker">
        <Plus :size="14" />
        페이지 추가
      </BaseButton>
      <BaseButton variant="secondary" size="sm">
        <Wand2 :size="14" />
        일괄 번역
      </BaseButton>
    </div>

    <!-- Drag overlay -->
    <div
      v-if="isDragging"
      class="border-2 border-dashed border-towa-accent rounded-lg p-8 mb-4 text-center text-towa-accent text-sm"
    >
      이미지를 여기에 드롭하여 페이지 추가
    </div>

    <div class="grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-4">
      <PageThumbnail
        v-for="page in pages"
        :key="page.id"
        :page="page"
        :selected="page.id === selectedPageId"
        @open-edit="$emit('openEdit', page.id)"
        @open-detail="$emit('openDetail', page.id)"
        @delete="$emit('deletePage', page.id)"
      />
    </div>
  </div>
</template>
