<script setup lang="ts">
import { computed, nextTick, ref, useTemplateRef } from 'vue'
import {
  Type, Trash2, Pencil, ALargeSmall, AlignVerticalSpaceAround,
  AlignLeft, AlignCenter, AlignRight,
  AlignStartVertical, AlignCenterVertical, AlignEndVertical,
} from 'lucide-vue-next'
import type { Layer, Text, TextAlign, TextVerticalAlign } from '@bitmappery/definitions/document'
import { getTextMeta } from '@/utils/text-layer'
import NumberCombo from './NumberCombo.vue'
import { SIZE_PRESETS, LINE_HEIGHT_PRESETS } from '@/constants/text-presets'

const HORIZONTAL_ALIGNS: Array<{ value: TextAlign; icon: typeof AlignLeft; title: string }> = [
  { value: 'left',   icon: AlignLeft,   title: '왼쪽 정렬' },
  { value: 'center', icon: AlignCenter, title: '가운데 정렬' },
  { value: 'right',  icon: AlignRight,  title: '오른쪽 정렬' },
]
const VERTICAL_ALIGNS: Array<{ value: TextVerticalAlign; icon: typeof AlignStartVertical; title: string }> = [
  { value: 'top',    icon: AlignStartVertical,  title: '상단 정렬' },
  { value: 'middle', icon: AlignCenterVertical, title: '가운데 정렬' },
  { value: 'bottom', icon: AlignEndVertical,    title: '하단 정렬' },
]

const props = defineProps<{
  layer: Layer
  selected: boolean
}>()

const emit = defineEmits<{
  select: []
  updateText: [textPatch: Partial<Text>]
  updateOriginal: [next: string]
  remove: []
}>()

const meta = computed(() => getTextMeta(props.layer))

const editingOriginal = ref(false)
const originalDraft = ref('')
const originalInput = useTemplateRef<HTMLInputElement>('originalInput')

async function startEditOriginal() {
  originalDraft.value = meta.value?.original ?? ''
  editingOriginal.value = true
  await nextTick()
  originalInput.value?.focus()
  originalInput.value?.select()
}

function commitOriginal() {
  if (!editingOriginal.value) return
  emit('updateOriginal', originalDraft.value)
  editingOriginal.value = false
}

function cancelOriginal() {
  editingOriginal.value = false
}

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

// Vue 3 reactivity flushes DOM updates on the next microtask. If the user
// clicks the same delete button fast enough — or clicks before the parent's
// v-for has reconciled — the second click hits the same stale element. The
// closure's layer.id is still the just-removed one; EditorTab.removeTextLayer
// short-circuits on idx === -1 and the click is effectively swallowed, while
// the user expected the *next* row to disappear.
//
// Guarding via a `:disabled` ref alone isn't enough — :disabled bindings
// apply on the next reactive flush, so two clicks dispatched in the same
// cycle both still go through. We also flip the DOM attribute directly so
// subsequent clicks at the same coords no-op even within the same tick.
const removing = ref(false)
function onRemove(e: MouseEvent) {
  if (removing.value) return
  removing.value = true
  const btn = e.currentTarget as HTMLButtonElement | null
  if (btn) btn.disabled = true
  emit('remove')
}
</script>

<template>
  <div
    :data-text-block-id="layer.id"
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
          class="p-0.5 rounded hover:bg-red-500/20 text-towa-text-muted hover:text-red-400 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          title="삭제"
          :disabled="removing"
          @click.stop="onRemove"
        >
          <Trash2 :size="12" />
        </button>
      </div>
    </div>
    <div v-if="original || selected" class="flex items-start gap-1 mb-1.5">
      <input
        v-if="editingOriginal"
        ref="originalInput"
        v-model="originalDraft"
        class="flex-1 bg-towa-bg border border-towa-accent rounded px-1.5 py-0.5 text-xs text-towa-text focus:outline-none"
        @keydown.enter.prevent="commitOriginal"
        @keydown.esc.prevent="cancelOriginal"
        @blur="commitOriginal"
        @click.stop
      />
      <p v-else class="flex-1 text-xs text-towa-text-muted leading-relaxed min-h-[18px]">
        {{ original || '원문 없음' }}
      </p>
      <button
        v-if="selected && !editingOriginal"
        class="p-0.5 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-accent transition-colors"
        title="원문 편집"
        @click.stop="startEditOriginal"
      >
        <Pencil :size="11" />
      </button>
    </div>
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
      <NumberCombo
        :model-value="layer.text.size"
        :icon="ALargeSmall"
        :presets="SIZE_PRESETS"
        :min="8"
        :max="200"
        title="크기"
        @update:model-value="(v) => $emit('updateText', { size: v })"
      />
      <NumberCombo
        :model-value="layer.text.lineHeight"
        :icon="AlignVerticalSpaceAround"
        :presets="LINE_HEIGHT_PRESETS"
        :min="0"
        :max="200"
        placeholder="자동"
        title="줄간격 (0 = 자동)"
        @update:model-value="(v) => $emit('updateText', { lineHeight: v })"
      />
      <input
        :value="layer.text.color"
        type="color"
        class="w-5 h-5 bg-transparent border border-towa-border rounded cursor-pointer"
        @input="$emit('updateText', { color: ($event.target as HTMLInputElement).value })"
        @click.stop
      />

      <div class="flex items-center gap-0.5 ml-auto">
        <button
          v-for="opt in HORIZONTAL_ALIGNS"
          :key="opt.value"
          :title="opt.title"
          class="p-1 rounded transition-colors"
          :class="layer.text.align === opt.value
            ? 'bg-towa-accent/20 text-towa-accent'
            : 'text-towa-text-muted hover:bg-towa-surface-light hover:text-towa-text'"
          @click.stop="$emit('updateText', { align: opt.value })"
        >
          <component :is="opt.icon" :size="13" />
        </button>
      </div>
      <div class="flex items-center gap-0.5">
        <button
          v-for="opt in VERTICAL_ALIGNS"
          :key="opt.value"
          :title="opt.title"
          class="p-1 rounded transition-colors"
          :class="layer.text.verticalAlign === opt.value
            ? 'bg-towa-accent/20 text-towa-accent'
            : 'text-towa-text-muted hover:bg-towa-surface-light hover:text-towa-text'"
          @click.stop="$emit('updateText', { verticalAlign: opt.value })"
        >
          <component :is="opt.icon" :size="13" />
        </button>
      </div>
    </div>
  </div>
</template>
