<script setup lang="ts">
import { computed } from 'vue'
import type { TextBlock } from '@/types/text-block'
import { Type } from 'lucide-vue-next'

const props = defineProps<{
  block: TextBlock
  selected: boolean
}>()

defineEmits<{
  select: []
  updateTranslation: [value: string]
}>()

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    detected: '검출됨',
    translated: '번역됨',
    edited: '수정됨',
  }
  return map[props.block.status] ?? props.block.status
})
</script>

<template>
  <div
    class="px-3 py-2.5 border-b border-towa-border cursor-pointer transition-colors"
    :class="selected ? 'bg-towa-accent/10 border-l-2 border-l-towa-accent' : 'hover:bg-towa-surface-light'"
    @click="$emit('select')"
  >
    <div class="flex items-center justify-between mb-1">
      <span class="text-[10px] text-towa-text-muted">{{ block.id.split('-').pop() }}</span>
      <span class="text-[10px] px-1.5 py-0.5 rounded bg-towa-surface-light text-towa-text-muted">
        {{ statusLabel }}
      </span>
    </div>
    <p class="text-xs text-towa-text-muted mb-1.5 leading-relaxed">{{ block.original }}</p>
    <textarea
      :value="block.translated"
      rows="2"
      class="w-full bg-towa-bg border border-towa-border rounded px-2 py-1.5 text-sm text-towa-text placeholder:text-towa-text-muted focus:outline-none focus:border-towa-accent resize-none"
      placeholder="번역문 입력..."
      @input="$emit('updateTranslation', ($event.target as HTMLTextAreaElement).value)"
      @click.stop
    />

    <!-- Font editing (shows when selected) -->
    <div v-if="selected" class="mt-2 flex items-center gap-2 flex-wrap" @click.stop>
      <div class="flex items-center gap-1">
        <Type :size="12" class="text-towa-text-muted" />
        <select
          :value="block.font"
          class="bg-towa-bg border border-towa-border rounded px-1.5 py-0.5 text-[11px] text-towa-text focus:outline-none focus:border-towa-accent"
        >
          <option value="Noto Sans KR">Noto Sans KR</option>
          <option value="Nanum Gothic">나눔고딕</option>
          <option value="Nanum Myeongjo">나눔명조</option>
          <option value="Black Han Sans">블랙한산스</option>
        </select>
      </div>
      <input
        :value="block.fontSize"
        type="number"
        min="8"
        max="72"
        class="w-12 bg-towa-bg border border-towa-border rounded px-1.5 py-0.5 text-[11px] text-towa-text text-center focus:outline-none focus:border-towa-accent"
        @click.stop
      />
      <input
        :value="block.color"
        type="color"
        class="w-5 h-5 bg-transparent border border-towa-border rounded cursor-pointer"
        @click.stop
      />
    </div>
  </div>
</template>
