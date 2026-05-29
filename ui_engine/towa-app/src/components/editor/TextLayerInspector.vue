<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, nextTick, useTemplateRef } from 'vue'
import { useStore } from 'vuex'
import {
  Type, Trash2, Plus,
  AlignLeft, AlignCenter, AlignRight,
  AlignStartVertical, AlignCenterVertical, AlignEndVertical,
} from 'lucide-vue-next'
import type { Layer, Text, TextAlign, TextVerticalAlign } from '@bitmappery/definitions/document'
import { LayerTypes } from '@bitmappery/definitions/layer-types'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'
// @ts-expect-error bitmappery JS module
import ToolTypes from '@bitmappery/definitions/tool-types'
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
const STATUS_LABEL: Record<string, string> = {
  detected: '검출됨',
  translated: '번역됨',
  edited: '수정됨',
}

const activeLayer = computed<Layer | null>(() => {
  const layer = store.getters['bmp/activeLayer'] as Layer | undefined
  return layer && isTextLayer(layer) ? layer : null
})
const activeIndex = computed<number>(() => store.getters['bmp/activeLayerIndex'] ?? -1)
const meta = computed(() => (activeLayer.value ? getTextMeta(activeLayer.value) : null))
const statusLabel = computed(() => (meta.value?.status ? STATUS_LABEL[meta.value.status] ?? meta.value.status : ''))
const idLabel = computed(() => {
  if (!activeLayer.value) return ''
  const blockId = meta.value?.blockId ?? activeLayer.value.id
  return blockId.split(/[-_]/).pop() ?? blockId
})
const horizIcon = computed(() => HORIZONTAL_ALIGNS.find(o => o.value === activeLayer.value?.text.align)?.icon ?? AlignCenter)
const vertIcon = computed(() => VERTICAL_ALIGNS.find(o => o.value === activeLayer.value?.text.verticalAlign)?.icon ?? AlignCenterVertical)

type Popover = 'original' | 'value' | 'font' | 'size' | 'align'
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
  const top = `${r.bottom + 4}px`
  if (open.value === 'original' || open.value === 'value') {
    return { position: 'fixed', top, left: `${r.left}px`, width: `${r.width}px` }
  }
  if (open.value === 'font') {
    return { position: 'fixed', top, left: `${r.left}px`, minWidth: `${Math.max(r.width, 160)}px` }
  }
  // size, align: 우측 정렬
  return { position: 'fixed', top, right: `${window.innerWidth - r.right}px` }
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

function removeLayer() {
  if (activeIndex.value < 0) return
  store.commit('bmp/removeLayer', activeIndex.value)
  store.commit('editor/SELECT_LAYER', null)
  markDirty()
}

function addEmptyTextLayer() {
  const doc = store.getters['bmp/activeDocument'] as { width?: number; height?: number; layers?: Layer[] } | undefined
  if (!doc) return
  const docW = doc.width ?? 800
  const docH = doc.height ?? 1200
  const width = Math.max(120, Math.min(300, Math.round(docW * 0.25)))
  const height = Math.max(60, Math.round(width * 0.4))
  const left = Math.round((docW - width) / 2)
  const top = Math.round((docH - height) / 2)
  const layer = LayerFactory.create({
    type: LayerTypes.LAYER_TEXT,
    left, top, width, height,
    transparent: true,
    visible: true,
    text: {
      value: '',
      font: 'Noto Sans KR',
      size: 24,
      unit: 'px',
      lineHeight: 0,
      spacing: 0,
      color: '#000000',
      align: 'center',
      verticalAlign: 'middle',
    },
  }) as Layer
  layer.meta = { blockId: layer.id, original: '', status: 'edited', boxMode: 'fixed' }
  store.commit('bmp/addLayer', layer)
  store.commit('editor/SELECT_LAYER', layer.id)
  store.commit('bmp/setActiveTool', { tool: ToolTypes.TEXT, document: doc })
  markDirty()
}
</script>

<template>
  <div ref="containerRef" class="space-y-1.5">
    <div v-if="!activeLayer" class="flex items-center gap-2">
      <div class="flex-1 rounded border border-dashed border-towa-border px-2 py-2 text-center text-[11px] text-towa-text-muted">
        선택된 텍스트 레이어 없음
      </div>
      <button
        class="p-1.5 rounded bg-towa-bg border border-towa-border hover:border-towa-accent text-towa-text-muted hover:text-towa-accent transition-colors"
        title="텍스트 블록 추가"
        @click="addEmptyTextLayer"
      >
        <Plus :size="14" />
      </button>
    </div>

    <template v-else>
      <div class="flex items-center justify-between text-[10px]">
        <div class="flex items-center gap-1.5">
          <span class="text-towa-text-muted font-mono">#{{ idLabel }}</span>
          <span v-if="statusLabel" class="px-1.5 py-0.5 rounded bg-towa-surface-light text-towa-text-muted">
            {{ statusLabel }}
          </span>
        </div>
        <div class="flex items-center gap-0.5">
          <button
            class="p-0.5 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-accent transition-colors"
            title="텍스트 블록 추가"
            @click="addEmptyTextLayer"
          >
            <Plus :size="12" />
          </button>
          <button
            class="p-0.5 rounded hover:bg-red-500/20 text-towa-text-muted hover:text-red-400 transition-colors"
            title="삭제"
            @click="removeLayer"
          >
            <Trash2 :size="12" />
          </button>
        </div>
      </div>

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

      <div class="flex items-center gap-1">
        <button
          class="flex-1 min-w-0 flex items-center gap-1 px-1.5 py-1 rounded bg-towa-bg border border-towa-border hover:border-towa-accent transition-colors"
          :class="{ 'border-towa-accent': open === 'font' }"
          :title="activeLayer.text.font"
          @click="togglePop('font', $event)"
        >
          <Type :size="11" class="text-towa-text-muted shrink-0" />
          <span class="flex-1 text-[10px] text-towa-text truncate text-left">{{ activeLayer.text.font }}</span>
        </button>

        <button
          class="px-2 py-1 rounded bg-towa-bg border border-towa-border hover:border-towa-accent transition-colors text-[10px] text-towa-text font-mono"
          :class="{ 'border-towa-accent': open === 'size' }"
          title="크기"
          @click="togglePop('size', $event)"
        >
          {{ activeLayer.text.size }}
        </button>

        <button
          class="relative w-7 h-7 rounded border border-towa-border hover:border-towa-accent transition-colors overflow-hidden shrink-0"
          title="색상"
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

        <button
          class="flex items-center px-1.5 py-1 rounded bg-towa-bg border border-towa-border hover:border-towa-accent transition-colors"
          :class="{ 'border-towa-accent': open === 'align' }"
          title="정렬"
          @click="togglePop('align', $event)"
        >
          <component :is="horizIcon" :size="12" class="text-towa-text" />
          <component :is="vertIcon" :size="12" class="text-towa-text -ml-0.5" />
        </button>
      </div>
    </template>

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

        <div v-else-if="open === 'font'" class="py-1">
          <button
            v-for="f in FONTS"
            :key="f"
            class="w-full text-left px-3 py-1.5 text-[11px] hover:bg-towa-surface-light"
            :class="activeLayer.text.font === f ? 'text-towa-accent' : 'text-towa-text'"
            @click="patchText({ font: f }); closePop()"
          >
            {{ f }}
          </button>
        </div>

        <div v-else-if="open === 'size'" class="p-2 w-[160px] space-y-1.5">
          <input
            :value="activeLayer.text.size"
            type="number"
            min="8"
            max="200"
            class="w-full bg-towa-bg border border-towa-border rounded px-2 py-1 text-xs text-towa-text text-center focus:outline-none focus:border-towa-accent"
            @input="patchText({ size: Number(($event.target as HTMLInputElement).value) })"
          />
          <input
            :value="activeLayer.text.size"
            type="range"
            min="8"
            max="120"
            step="1"
            class="w-full accent-towa-accent"
            @input="patchText({ size: Number(($event.target as HTMLInputElement).value) })"
          />
        </div>

        <div v-else-if="open === 'align'" class="p-2 space-y-1.5">
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
    </Teleport>
  </div>
</template>
