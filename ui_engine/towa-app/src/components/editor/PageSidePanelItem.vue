<script setup lang="ts">
import { computed } from 'vue'
import type { Page } from '@/types/page'
import { useThumbnailUrl } from '@/composables/useThumbnailUrl'
import { useDirtyState } from '@/composables/useAutoSave'

const props = defineProps<{
  page: Page
  active: boolean
  statusColor: string
}>()

defineEmits<{
  select: []
}>()

// useThumbnailUrl owns the Object URL lifecycle per #39. Splitting each
// thumbnail into its own component is required because composables can't
// be called inside v-for in the parent.
const pageId = computed(() => props.page.id)
const { url } = useThumbnailUrl(pageId)

const { dirty, dirtyPageId } = useDirtyState()
const isDirty = computed(() => dirty.value && dirtyPageId.value === props.page.id)
</script>

<template>
  <button
    class="rounded-md overflow-hidden border-2 transition-colors"
    :class="active ? 'border-towa-accent' : 'border-transparent hover:border-towa-surface-light'"
    @click="$emit('select')"
  >
    <div class="relative">
      <img
        v-if="url"
        :src="url"
        :alt="`${page.index}p`"
        class="w-full aspect-[2/3] object-cover"
      />
      <div v-else class="w-full aspect-[2/3] bg-towa-bg flex items-center justify-center text-towa-text-muted text-xs">
        {{ page.index }}p
      </div>
      <span
        v-if="isDirty"
        class="absolute top-1 left-1 text-[8px] font-medium text-white px-1 py-0.5 rounded bg-towa-warning"
        title="저장되지 않은 변경분이 있습니다"
      >
        저장 안 됨
      </span>
      <span
        class="absolute top-1 right-1 text-[8px] font-medium text-white px-1 py-0.5 rounded"
        :class="statusColor"
      >
        {{ page.index }}p
      </span>
    </div>
  </button>
</template>
