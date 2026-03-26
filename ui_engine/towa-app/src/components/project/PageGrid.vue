<script setup lang="ts">
import type { Page } from '@/types/page'
import { Plus, Wand2 } from 'lucide-vue-next'
import BaseButton from '@/components/common/BaseButton.vue'
import PageThumbnail from './PageThumbnail.vue'

defineProps<{
  pages: Page[]
  selectedPageId: string | null
}>()

defineEmits<{
  openEdit: [pageId: string]
  openDetail: [pageId: string]
}>()
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-4">
      <BaseButton variant="secondary" size="sm">
        <Plus :size="14" />
        페이지 추가
      </BaseButton>
      <BaseButton variant="secondary" size="sm">
        <Wand2 :size="14" />
        일괄 번역
      </BaseButton>
    </div>

    <div class="grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-4">
      <PageThumbnail
        v-for="page in pages"
        :key="page.id"
        :page="page"
        :selected="page.id === selectedPageId"
        @open-edit="$emit('openEdit', page.id)"
        @open-detail="$emit('openDetail', page.id)"
      />
    </div>
  </div>
</template>
