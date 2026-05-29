<script setup lang="ts">
// 편집 화면(③) 우측 번역 패널 헤더에 들어가는 작은 컨트롤.
// 인페인트 레이어 전체의 가시성 토글 + 투명도 일괄 조절 popover.
import { computed, ref, onMounted, onBeforeUnmount, useTemplateRef } from 'vue'
import { useStore } from 'vuex'
import { Eye, EyeOff, SprayCan } from 'lucide-vue-next'
import type { Layer } from '@bitmappery/definitions/document'
import { classifyLayer } from '@/utils/layer-classify'
import { useAutoSave } from '@/composables/useAutoSave'

const store = useStore()
const { markDirty } = useAutoSave()

interface InpaintEntry { index: number; layer: Layer }

const inpaintEntries = computed<InpaintEntry[]>(() => {
  const doc = store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  return (doc?.layers ?? [])
    .map((layer, index) => ({ index, layer }))
    .filter((e) => classifyLayer(e.layer) === 'inpaint')
})

const hasInpaint = computed(() => inpaintEntries.value.length > 0)

// 가시성: 하나라도 켜져 있으면 "켜짐" 상태로 본다. 토글 시 모두 같은 값으로.
const anyVisible = computed(() => inpaintEntries.value.some((e) => e.layer.visible !== false))

// bitmappery는 layer.filters.opacity + filters.enabled 조합으로 alpha 처리.
// layer.opacity는 사용 안 함. (layer-renderer.ts:666 참조)
function layerOpacity(layer: Layer): number {
  const f = layer.filters as { enabled?: boolean; opacity?: number } | undefined
  if (!f || f.enabled === false) return 1
  return typeof f.opacity === 'number' ? f.opacity : 1
}

const opacity = computed<number>(() => {
  const entries = inpaintEntries.value
  if (entries.length === 0) return 1
  const sum = entries.reduce((acc, e) => acc + layerOpacity(e.layer), 0)
  return sum / entries.length
})

const open = ref(false)
const triggerEl = useTemplateRef<HTMLButtonElement>('triggerEl')
const popoverEl = useTemplateRef<HTMLElement>('popoverEl')

const popoverStyle = computed<Record<string, string>>(() => {
  if (!open.value || !triggerEl.value) return { display: 'none' }
  const r = triggerEl.value.getBoundingClientRect()
  return {
    position: 'fixed',
    top: `${r.bottom + 4}px`,
    right: `${window.innerWidth - r.right}px`,
  }
})

function toggleOpen() { open.value = !open.value }
function close() { open.value = false }

function toggleVisible() {
  const next = !anyVisible.value
  for (const e of inpaintEntries.value) {
    if (e.layer.visible !== next) {
      store.commit('bmp/updateLayer', { index: e.index, opts: { visible: next } })
    }
  }
  markDirty()
}

function setOpacity(value: number) {
  const clamped = Math.max(0, Math.min(1, value))
  for (const e of inpaintEntries.value) {
    const prev = (e.layer.filters as Record<string, unknown> | undefined) ?? {}
    const nextFilters = { ...prev, enabled: true, opacity: clamped }
    store.commit('bmp/updateLayer', { index: e.index, opts: { filters: nextFilters } })
  }
  markDirty()
}

function onDocClick(e: MouseEvent) {
  if (!open.value) return
  const t = e.target as Node
  if (triggerEl.value?.contains(t)) return
  if (popoverEl.value?.contains(t)) return
  close()
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && open.value) { e.stopPropagation(); close() }
}
onMounted(() => {
  document.addEventListener('mousedown', onDocClick)
  document.addEventListener('keydown', onKeydown)
  window.addEventListener('resize', close)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick)
  document.removeEventListener('keydown', onKeydown)
  window.removeEventListener('resize', close)
})
</script>

<template>
  <div class="relative">
    <button
      ref="triggerEl"
      class="p-1 rounded transition-colors"
      :class="hasInpaint
        ? (open ? 'bg-towa-accent/20 text-towa-accent' : 'hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-accent')
        : 'text-towa-text-muted/40 cursor-not-allowed'"
      :disabled="!hasInpaint"
      :title="hasInpaint ? `인페인트 레이어 (${inpaintEntries.length})` : '인페인트 레이어 없음'"
      @click="toggleOpen"
    >
      <SprayCan :size="14" />
    </button>

    <Teleport to="body">
      <div
        v-if="open && hasInpaint"
        ref="popoverEl"
        :style="popoverStyle"
        class="z-[100] bg-towa-surface border border-towa-accent rounded shadow-xl p-3 w-[220px] space-y-2"
      >
        <div class="flex items-center justify-between">
          <span class="text-[11px] text-towa-text-muted">인페인트 ({{ inpaintEntries.length }})</span>
          <button
            class="flex items-center gap-1 px-2 py-1 rounded text-[11px] hover:bg-towa-surface-light transition-colors"
            :class="anyVisible ? 'text-towa-text' : 'text-towa-text-muted'"
            :title="anyVisible ? '모두 숨기기' : '모두 표시'"
            @click="toggleVisible"
          >
            <component :is="anyVisible ? Eye : EyeOff" :size="12" />
            <span>{{ anyVisible ? '표시' : '숨김' }}</span>
          </button>
        </div>

        <div class="space-y-1">
          <div class="flex items-center justify-between text-[10px] text-towa-text-muted">
            <span>투명도</span>
            <span class="font-mono text-towa-text">{{ Math.round(opacity * 100) }}%</span>
          </div>
          <input
            :value="opacity"
            type="range"
            min="0"
            max="1"
            step="0.01"
            class="w-full accent-towa-accent"
            @input="setOpacity(Number(($event.target as HTMLInputElement).value))"
          />
        </div>
      </div>
    </Teleport>
  </div>
</template>
