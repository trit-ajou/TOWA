<script setup lang="ts">
import {
  ref, computed, onMounted, onBeforeUnmount, useTemplateRef, type Component,
} from 'vue'

interface Preset { label: string; value: number }

const props = withDefaults(defineProps<{
  modelValue: number
  presets?: Preset[]
  icon?: Component
  /** 값이 0(또는 falsy)일 때 인풋에 표시할 placeholder. 지정 시 0은 빈칸으로 보임. */
  placeholder?: string
  min?: number
  max?: number
  title?: string
  /** 인풋 너비 Tailwind 클래스 */
  width?: string
}>(), {
  presets: () => [],
  min: 0,
  max: 999,
  width: 'w-12',
})

const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

const rootRef = useTemplateRef<HTMLElement>('rootRef')
const inputRef = useTemplateRef<HTMLInputElement>('inputRef')
const menuRef = useTemplateRef<HTMLElement>('menuRef')

const open = ref(false)
const menuStyle = ref<Record<string, string>>({})

// placeholder가 있으면 0은 빈칸으로 노출 (예: 줄간격 "자동")
const shownValue = computed<number | ''>(() =>
  props.placeholder && !props.modelValue ? '' : props.modelValue,
)

function updateMenuPos() {
  const el = rootRef.value
  if (!el) return
  const r = el.getBoundingClientRect()
  menuStyle.value = {
    position: 'fixed',
    top: `${r.bottom + 4}px`,
    left: `${r.left}px`,
    minWidth: `${Math.max(r.width, 72)}px`,
  }
}

function openMenu() {
  if (props.presets.length === 0) return
  updateMenuPos()
  open.value = true
}
function closeMenu() { open.value = false }

function onInput(e: Event) {
  const v = Number((e.target as HTMLInputElement).value)
  emit('update:modelValue', Number.isFinite(v) ? v : 0)
}

// @mousedown.prevent로 인풋 blur를 막아 포커스를 유지한 채 값만 교체.
function pickPreset(p: Preset) {
  emit('update:modelValue', p.value)
  closeMenu()
}

function onDocPointer(e: PointerEvent) {
  if (!open.value) return
  const t = e.target as Node
  if (rootRef.value?.contains(t) || menuRef.value?.contains(t)) return
  closeMenu()
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && open.value) { e.stopPropagation(); closeMenu() }
}
// 패널 스크롤 시 fixed 메뉴 좌표가 어긋나므로 닫음 (TextLayerInspector와 동일 전략)
function onScroll() { if (open.value) closeMenu() }

onMounted(() => {
  document.addEventListener('pointerdown', onDocPointer, true)
  document.addEventListener('keydown', onKeydown)
  window.addEventListener('scroll', onScroll, true)
  window.addEventListener('resize', closeMenu)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocPointer, true)
  document.removeEventListener('keydown', onKeydown)
  window.removeEventListener('scroll', onScroll, true)
  window.removeEventListener('resize', closeMenu)
})
</script>

<template>
  <div ref="rootRef" class="flex items-center gap-0.5" :title="title">
    <component :is="icon" v-if="icon" :size="12" class="text-towa-text-muted shrink-0" />
    <input
      ref="inputRef"
      :value="shownValue"
      type="number"
      :min="min"
      :max="max"
      :placeholder="placeholder"
      :class="width"
      class="bg-towa-bg border border-towa-border rounded px-1.5 py-0.5 text-[11px] text-towa-text text-center placeholder:text-towa-text-muted focus:outline-none focus:border-towa-accent"
      @focus="openMenu"
      @click.stop="openMenu"
      @input="onInput"
    />
  </div>

  <Teleport to="body">
    <div
      v-if="open"
      ref="menuRef"
      :style="menuStyle"
      class="z-[100] max-h-56 overflow-y-auto bg-towa-surface border border-towa-accent rounded shadow-xl py-1"
    >
      <button
        v-for="p in presets"
        :key="p.label"
        type="button"
        class="w-full text-left px-3 py-1 text-[11px] hover:bg-towa-surface-light"
        :class="p.value === modelValue ? 'text-towa-accent' : 'text-towa-text'"
        @mousedown.prevent="pickPreset(p)"
      >
        {{ p.label }}
      </button>
    </div>
  </Teleport>
</template>
