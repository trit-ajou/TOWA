<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, nextTick, useTemplateRef } from 'vue'
import { useStore } from 'vuex'
import {
  Type, ALargeSmall, AlignVerticalSpaceAround,
  AlignLeft, AlignCenter, AlignRight,
  AlignStartVertical, AlignCenterVertical, AlignEndVertical,
} from 'lucide-vue-next'
import type { Layer, Text, TextAlign, TextVerticalAlign } from '@bitmappery/definitions/document'
import { isTextLayer, getTextMeta, mergeTextMeta } from '@/utils/text-layer'
import { useAutoSave } from '@/composables/useAutoSave'

const store = useStore()
const { markDirty } = useAutoSave()

const FONTS = ['Noto Sans KR', 'Nanum Gothic', 'Nanum Myeongjo', 'Black Han Sans']
const HORIZONTAL_ALIGNS: Array<{ value: TextAlign; icon: typeof AlignLeft; title: string }> = [
  { value: 'left',   icon: AlignLeft,   title: '왼쪽' },
  { value: 'center', icon: AlignCenter, title: '가운데' },
  { value: 'right',  icon: AlignRight,  title: '오른쪽' },
]
const VERTICAL_ALIGNS: Array<{ value: TextVerticalAlign; icon: typeof AlignStartVertical; title: string }> = [
  { value: 'top',    icon: AlignStartVertical,  title: '상단' },
  { value: 'middle', icon: AlignCenterVertical, title: '중간' },
  { value: 'bottom', icon: AlignEndVertical,    title: '하단' },
]

const activeLayer = computed<Layer | null>(() => {
  const layer = store.getters['bmp/activeLayer'] as Layer | undefined
  return layer && isTextLayer(layer) ? layer : null
})
const activeIndex = computed<number>(() => store.getters['bmp/activeLayerIndex'] ?? -1)
const meta = computed(() => (activeLayer.value ? getTextMeta(activeLayer.value) : null))

// 원문/번역 내용 편집만 popover (긴 텍스트라 인라인 부적합). 속성은 모두 펼쳐 노출.
type Popover = 'original' | 'value'
const open = ref<Popover | null>(null)
const triggerEl = ref<HTMLElement | null>(null)
const containerRef = useTemplateRef<HTMLElement>('containerRef')
const popoverEl = useTemplateRef<HTMLElement>('popoverEl')
const originalTa = useTemplateRef<HTMLTextAreaElement>('originalTa')
const valueTa = useTemplateRef<HTMLTextAreaElement>('valueTa')
const colorInput = useTemplateRef<HTMLInputElement>('colorInput')

const popoverStyle = computed<Record<string, string>>(() => {
  if (!open.value || !triggerEl.value) return { display: 'none' }
  const r = triggerEl.value.getBoundingClientRect()
  return { position: 'fixed', top: `${r.bottom + 4}px`, left: `${r.left}px`, width: `${r.width}px` }
})

async function togglePop(name: Popover, e: MouseEvent) {
  const next = open.value === name ? null : name
  open.value = next
  triggerEl.value = next ? (e.currentTarget as HTMLElement) : null
  if (next === 'original') { await nextTick(); originalTa.value?.focus() }
  else if (next === 'value') { await nextTick(); valueTa.value?.focus() }
}
function closePop() {
  open.value = null
  triggerEl.value = null
}

function onDocClick(e: MouseEvent) {
  if (!open.value) return
  const t = e.target as Node
  if (containerRef.value?.contains(t)) return
  if (popoverEl.value?.contains(t)) return
  closePop()
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && open.value) { e.stopPropagation(); closePop() }
}
function onScroll() {
  // 패널이 스크롤되면 fixed popover 좌표가 어긋나므로 닫음
  if (open.value) closePop()
}

onMounted(() => {
  document.addEventListener('mousedown', onDocClick)
  document.addEventListener('keydown', onKeydown)
  window.addEventListener('scroll', onScroll, true)
  window.addEventListener('resize', closePop)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick)
  document.removeEventListener('keydown', onKeydown)
  window.removeEventListener('scroll', onScroll, true)
  window.removeEventListener('resize', closePop)
})

function patchText(textPatch: Partial<Text>) {
  if (!activeLayer.value || activeIndex.value < 0) return
  const nextText: Text = { ...activeLayer.value.text, ...textPatch }
  const nextMeta = mergeTextMeta(activeLayer.value, { status: 'edited' })
  store.commit('bmp/updateLayer', { index: activeIndex.value, opts: { text: nextText, meta: nextMeta } })
  markDirty()
}

function patchOriginal(next: string) {
  if (!activeLayer.value || activeIndex.value < 0) return
  const nextMeta = mergeTextMeta(activeLayer.value, { original: next, status: 'edited' })
  store.commit('bmp/updateLayer', { index: activeIndex.value, opts: { meta: nextMeta } })
  markDirty()
}
</script>

<template>
  <div ref="containerRef">
    <div v-if="!activeLayer" class="rounded border border-dashed border-towa-border px-2 py-3 text-center text-[11px] text-towa-text-muted">
      선택된 텍스트 레이어 없음
    </div>

    <div v-else class="space-y-2.5">
      <!-- 원문 / 번역: 내용 편집은 popover -->
      <button
        class="w-full flex items-center gap-2 px-2 py-1.5 rounded bg-towa-bg border border-towa-border hover:border-towa-accent transition-colors text-left"
        :class="{ 'border-towa-accent': open === 'original' }"
        @click="togglePop('original', $event)"
      >
        <span class="text-[10px] text-towa-text-muted shrink-0">원문</span>
        <span class="flex-1 text-xs text-towa-text-muted truncate">{{ meta?.original || '—' }}</span>
      </button>

      <button
        class="w-full flex items-center gap-2 px-2 py-1.5 rounded bg-towa-bg border border-towa-border hover:border-towa-accent transition-colors text-left"
        :class="{ 'border-towa-accent': open === 'value' }"
        @click="togglePop('value', $event)"
      >
        <span class="text-[10px] text-towa-text-muted shrink-0">번역</span>
        <span
          class="flex-1 text-xs truncate"
          :class="activeLayer.text.value ? 'text-towa-text' : 'text-towa-text-muted'"
        >
          {{ activeLayer.text.value || '번역문 입력...' }}
        </span>
      </button>

      <div class="border-t border-towa-border" />

      <!-- 폰트 -->
      <div class="flex items-center gap-2">
        <Type :size="13" class="text-towa-text-muted shrink-0" />
        <select
          :value="activeLayer.text.font"
          class="flex-1 min-w-0 bg-towa-bg border border-towa-border rounded px-1.5 py-1 text-[11px] text-towa-text focus:outline-none focus:border-towa-accent"
          @change="patchText({ font: ($event.target as HTMLSelectElement).value })"
        >
          <option v-for="f in FONTS" :key="f" :value="f">{{ f }}</option>
        </select>
      </div>

      <!-- 크기 · 줄간격 · 색 (한 줄) -->
      <div class="flex items-center gap-2">
        <div class="flex items-center gap-1.5 flex-1 min-w-0" title="크기">
          <ALargeSmall :size="14" class="text-towa-text-muted shrink-0" />
          <input
            :value="activeLayer.text.size"
            type="number"
            min="8"
            max="200"
            class="w-full min-w-0 bg-towa-bg border border-towa-border rounded px-2 py-1 text-xs text-towa-text text-center focus:outline-none focus:border-towa-accent"
            @input="patchText({ size: Number(($event.target as HTMLInputElement).value) })"
          />
        </div>
        <div class="flex items-center gap-1.5 flex-1 min-w-0" title="줄간격 (비우면 자동)">
          <AlignVerticalSpaceAround :size="14" class="text-towa-text-muted shrink-0" />
          <input
            :value="activeLayer.text.lineHeight || ''"
            type="number"
            min="0"
            max="200"
            placeholder="자동"
            class="w-full min-w-0 bg-towa-bg border border-towa-border rounded px-2 py-1 text-xs text-towa-text text-center placeholder:text-towa-text-muted focus:outline-none focus:border-towa-accent"
            @input="patchText({ lineHeight: Number(($event.target as HTMLInputElement).value) || 0 })"
          />
        </div>
        <button
          class="relative w-8 h-8 rounded border border-towa-border hover:border-towa-accent transition-colors overflow-hidden shrink-0"
          :title="`색상 ${activeLayer.text.color}`"
          @click="colorInput?.click()"
        >
          <span class="absolute inset-0.5 rounded-sm" :style="{ backgroundColor: activeLayer.text.color }" />
          <input
            ref="colorInput"
            :value="activeLayer.text.color"
            type="color"
            class="absolute opacity-0 w-0 h-0 pointer-events-none"
            @input="patchText({ color: ($event.target as HTMLInputElement).value })"
          />
        </button>
      </div>

      <!-- 정렬 -->
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-[11px] text-towa-text-muted">정렬</span>
        <div class="flex items-center gap-0.5">
          <button
            v-for="opt in HORIZONTAL_ALIGNS"
            :key="opt.value"
            :title="opt.title"
            class="p-1.5 rounded transition-colors"
            :class="activeLayer.text.align === opt.value
              ? 'bg-towa-accent/20 text-towa-accent'
              : 'text-towa-text-muted hover:bg-towa-surface-light hover:text-towa-text'"
            @click="patchText({ align: opt.value })"
          >
            <component :is="opt.icon" :size="14" />
          </button>
        </div>
        <div class="flex items-center gap-0.5">
          <button
            v-for="opt in VERTICAL_ALIGNS"
            :key="opt.value"
            :title="opt.title"
            class="p-1.5 rounded transition-colors"
            :class="activeLayer.text.verticalAlign === opt.value
              ? 'bg-towa-accent/20 text-towa-accent'
              : 'text-towa-text-muted hover:bg-towa-surface-light hover:text-towa-text'"
            @click="patchText({ verticalAlign: opt.value })"
          >
            <component :is="opt.icon" :size="14" />
          </button>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="open && activeLayer"
        ref="popoverEl"
        :style="popoverStyle"
        class="z-[100] bg-towa-surface border border-towa-accent rounded shadow-xl"
      >
        <div v-if="open === 'original'" class="p-2">
          <textarea
            ref="originalTa"
            :value="meta?.original ?? ''"
            rows="4"
            class="w-full bg-towa-bg border border-towa-border rounded px-2 py-1.5 text-xs text-towa-text focus:outline-none focus:border-towa-accent resize-none"
            placeholder="원문 입력"
            @input="patchOriginal(($event.target as HTMLTextAreaElement).value)"
          />
        </div>

        <div v-else-if="open === 'value'" class="p-2">
          <textarea
            ref="valueTa"
            :value="activeLayer.text.value"
            rows="4"
            class="w-full bg-towa-bg border border-towa-border rounded px-2 py-1.5 text-sm text-towa-text focus:outline-none focus:border-towa-accent resize-none"
            placeholder="번역문 입력"
            @input="patchText({ value: ($event.target as HTMLTextAreaElement).value })"
          />
        </div>
      </div>
    </Teleport>
  </div>
</template>
