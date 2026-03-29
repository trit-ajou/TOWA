<script setup lang="ts">
import type { TextBlock } from '@/types/text-block'
import TextBlockItem from './TextBlockItem.vue'

defineProps<{
  blocks: TextBlock[]
  selectedBlockId: string | null
}>()

defineEmits<{
  selectBlock: [id: string]
  updateTranslation: [blockId: string, value: string]
}>()
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="px-3 py-2 border-b border-towa-border">
      <h3 class="text-xs font-semibold text-towa-text-muted uppercase tracking-wider">
        텍스트 블록 ({{ blocks.length }})
      </h3>
    </div>
    <div class="flex-1 overflow-y-auto">
      <TextBlockItem
        v-for="block in blocks"
        :key="block.id"
        :block="block"
        :selected="block.id === selectedBlockId"
        @select="$emit('selectBlock', block.id)"
        @update-translation="(val) => $emit('updateTranslation', block.id, val)"
      />
      <div v-if="blocks.length === 0" class="p-4 text-center text-sm text-towa-text-muted">
        텍스트 블록이 없습니다
      </div>
    </div>
  </div>
</template>
