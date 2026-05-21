<script setup lang="ts">
import { computed } from 'vue'
import { Type, Trash2 } from 'lucide-vue-next'
import type { Layer, Text } from '@bitmappery/definitions/document'
import { getTextMeta } from '@/utils/text-layer'

const props = defineProps<{
  layer: Layer
  selected: boolean
}>()

defineEmits<{
  select: []
  updateText: [textPatch: Partial<Text>]
  remove: []
}>()

const meta = computed(() => getTextMeta(props.layer))

const statusLabel = computed(() => {
  const status = meta.value?.status
  const map: Record<string, string> = {
    detected: '검출됨',
    translated: '번역됨',
    edited: '수정됨',
  }
  return status ? map[status] ?? status : ''
})

const original = computed(() => meta.value?.original ?? '')
const idLabel = computed(() => {
  const blockId = meta.value?.blockId ?? props.layer.id
  const tail = blockId.split(/[-_]/).pop()
  return tail ?? blockId
})
</script>

<template>
  <div
    class="px-3 py-2.5 border-b border-towa-border cursor-pointer transition-colors"
    :class="selected ? 'bg-towa-accent/10 border-l-2 border-l-towa-accent' : 'hover:bg-towa-surface-light'"
    @click="$emit('select')"
  >
    <div class="flex items-center justify-between mb-1">
      <span class="text-[10px] text-towa-text-muted">{{ idLabel }}</span>
      <div class="flex items-center gap-1.5">
        <span v-if="statusLabel" class="text-[10px] px-1.5 py-0.5 rounded bg-towa-surface-light text-towa-text-muted">
          {{ statusLabel }}
        </span>
        <button
          class="p-0.5 rounded hover:bg-red-500/20 text-towa-text-muted hover:text-red-400 transition-colors"
          title="삭제"
          @click.stop="$emit('remove')"
        >
          <Trash2 :size="12" />
        </button>
      </div>
    </div>
    <p v-if="original" class="text-xs text-towa-text-muted mb-1.5 leading-relaxed">{{ original }}</p>
    <textarea
      :value="layer.text.value"
      rows="2"
      class="w-full bg-towa-bg border border-towa-border rounded px-2 py-1.5 text-sm text-towa-text placeholder:text-towa-text-muted focus:outline-none focus:border-towa-accent resize-none"
      placeholder="번역문 입력..."
      @input="$emit('updateText', { value: ($event.target as HTMLTextAreaElement).value })"
      @click.stop
    />

    <!-- Font editing (shows when selected) -->
    <div v-if="selected" class="mt-2 flex items-center gap-2 flex-wrap" @click.stop>
      <div class="flex items-center gap-1">
        <Type :size="12" class="text-towa-text-muted" />
        <select
          :value="layer.text.font"
          class="bg-towa-bg border border-towa-border rounded px-1.5 py-0.5 text-[11px] text-towa-text focus:outline-none focus:border-towa-accent"
          @change="$emit('updateText', { font: ($event.target as HTMLSelectElement).value })"
        >
          <option value="Noto Sans KR">Noto Sans KR</option>
          <option value="Nanum Gothic">나눔고딕</option>
          <option value="Nanum Myeongjo">나눔명조</option>
          <option value="Black Han Sans">블랙한산스</option>
        </select>
      </div>
      <input
        :value="layer.text.size"
        type="number"
        min="8"
        max="72"
        class="w-12 bg-towa-bg border border-towa-border rounded px-1.5 py-0.5 text-[11px] text-towa-text text-center focus:outline-none focus:border-towa-accent"
        @input="$emit('updateText', { size: Number(($event.target as HTMLInputElement).value) })"
        @click.stop
      />
      <input
        :value="layer.text.color"
        type="color"
        class="w-5 h-5 bg-transparent border border-towa-border rounded cursor-pointer"
        @input="$emit('updateText', { color: ($event.target as HTMLInputElement).value })"
        @click.stop
      />
    </div>
  </div>
</template>
