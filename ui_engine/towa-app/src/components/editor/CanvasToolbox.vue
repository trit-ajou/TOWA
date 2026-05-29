<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useStore } from 'vuex'
import {
  Hand, Move, ZoomIn, BoxSelect, Wand2, Brush, Stamp, Eraser,
  PaintBucket, Pipette, Type, RotateCw, Scaling, ArrowLeftRight,
  ScanText, Languages, Sparkles, GripHorizontal,
} from 'lucide-vue-next'
// @ts-expect-error bitmappery JS module
import ToolTypes from '@bitmappery/definitions/tool-types'
import { isFeatureEnabled, type FeatureKey } from '@bitmappery/config/towa-features'
import { useAiActions } from '@/composables/useAiActions'
import type { AiOperationKind } from '@/backend/contracts'

type ToolKey =
  | 'move' | 'drag' | 'zoom' | 'selection' | 'wand'
  | 'brush' | 'clone' | 'eraser' | 'fill' | 'eyedropper'
  | 'text' | 'rotate' | 'scale'

interface ToolDef {
  type: ToolKey
  label: string
  shortcut: string
  icon: typeof Hand
  flag: FeatureKey
}

const TOOLS: ToolDef[] = [
  { type: 'move',       label: '화면 이동',   shortcut: 'Space', icon: Hand,         flag: 'TOOL_MOVE' },
  { type: 'drag',       label: '객체 이동',   shortcut: 'V',     icon: Move,         flag: 'TOOL_DRAG' },
  { type: 'zoom',       label: '줌',         shortcut: 'Z',     icon: ZoomIn,       flag: 'TOOL_ZOOM' },
  { type: 'selection',  label: '사각 선택',   shortcut: 'M',     icon: BoxSelect,    flag: 'TOOL_SELECTION' },
  { type: 'wand',       label: '마법사 선택', shortcut: 'W',     icon: Wand2,        flag: 'TOOL_WAND' },
  { type: 'brush',      label: '브러쉬',     shortcut: 'B',     icon: Brush,        flag: 'TOOL_BRUSH' },
  { type: 'clone',      label: '도장',       shortcut: 'S',     icon: Stamp,        flag: 'TOOL_CLONE' },
  { type: 'eraser',     label: '지우개',     shortcut: 'E',     icon: Eraser,       flag: 'TOOL_ERASER' },
  { type: 'fill',       label: '페인트 통',  shortcut: 'G',     icon: PaintBucket,  flag: 'TOOL_FILL' },
  { type: 'eyedropper', label: '스포이드',   shortcut: 'I',     icon: Pipette,      flag: 'TOOL_EYEDROPPER' },
  { type: 'text',       label: '텍스트',     shortcut: 'T',     icon: Type,         flag: 'TOOL_TEXT' },
  { type: 'rotate',     label: '회전',       shortcut: 'R',     icon: RotateCw,     flag: 'TOOL_ROTATE' },
  { type: 'scale',      label: '변형',       shortcut: 'D',     icon: Scaling,      flag: 'TOOL_SCALE' },
]

interface AiActionDef {
  id: AiOperationKind
  label: string
  icon: typeof ScanText
}

const AI_ACTIONS: AiActionDef[] = [
  { id: 'detect',    label: '텍스트 검출', icon: ScanText },
  { id: 'inpaint',   label: '인페인팅',   icon: Sparkles },
  { id: 'translate', label: '번역',       icon: Languages },
]

const store = useStore()
const activeTool = computed<string | null>(() => store.getters['bmp/activeTool'])
const activeColor = computed<string>(() => store.getters['bmp/activeColor'] ?? '#000000')
const backgroundColor = computed<string>(() => store.getters['editor/backgroundColor'] ?? '#ffffff')
const activeDocument = computed(() => store.getters['bmp/activeDocument'])

const visibleTools = computed(() => TOOLS.filter(t => isFeatureEnabled(t.flag)))

const { loading: aiLoading, runAction: runAi } = useAiActions()

function selectTool(t: ToolDef) {
  if (!activeDocument.value) return
  const tool = (ToolTypes as Record<string, string>)[t.type.toUpperCase()]
  store.commit('bmp/setActiveTool', { tool, document: activeDocument.value })
}

function swapColors() {
  const fg = activeColor.value
  const bg = backgroundColor.value
  store.commit('bmp/setActiveColor', bg)
  store.commit('editor/SET_BACKGROUND_COLOR', fg)
}

// ─── 단축키 (도구 선택 + 색 swap) ───
// bitmappery KeyboardService와 충돌 피하려 input/textarea/contentEditable 포커스 시 무시.
// 도구 선택 단축키는 spec(canvas_ui_specs.md) 기준. TOOLS 배열의 shortcut 필드를 그대로 매핑.
function isTextInputFocused(): boolean {
  const t = document.activeElement as HTMLElement | null
  if (!t) return false
  return t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable
}

function onShortcut(e: KeyboardEvent) {
  if (e.ctrlKey || e.metaKey || e.altKey) return
  if (isTextInputFocused()) return
  // 한글 입력 시 e.key는 한글, e.code는 'KeyX' 등. code로 매칭하면 IME 무관.
  const code = e.code
  if (code === 'KeyX') {
    e.preventDefault()
    swapColors()
    return
  }
  const tool = TOOLS.find(t => `Key${t.shortcut.toUpperCase()}` === code)
  if (tool && activeDocument.value) {
    e.preventDefault()
    selectTool(tool)
  }
}

// ─── AI 드롭다운 ───
const aiMenuOpen = ref(false)
const aiButtonRef = ref<HTMLElement | null>(null)

function toggleAiMenu() {
  aiMenuOpen.value = !aiMenuOpen.value
}
function selectAi(id: AiOperationKind) {
  aiMenuOpen.value = false
  runAi(id)
}
function onDocClick(e: MouseEvent) {
  if (!aiMenuOpen.value) return
  const target = e.target as Node
  if (aiButtonRef.value && !aiButtonRef.value.contains(target)) {
    aiMenuOpen.value = false
  }
}

// ─── Floating drag ───
// 기본 위치: 좌측 하단 (mount 시 부모 사이즈 측정해서 계산)
const asideRef = ref<HTMLElement | null>(null)
const pos = ref({ left: 12, top: 12 })
const dragging = ref(false)
let dragOffsetX = 0
let dragOffsetY = 0

function onDragStart(e: PointerEvent) {
  dragging.value = true
  const rect = (e.currentTarget as HTMLElement).closest('aside')?.getBoundingClientRect()
  if (!rect) return
  dragOffsetX = e.clientX - rect.left
  dragOffsetY = e.clientY - rect.top
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}
function onDragMove(e: PointerEvent) {
  if (!dragging.value) return
  // canvas-area 컨테이너 기준 좌표
  const container = (e.currentTarget as HTMLElement).closest('aside')?.parentElement
  if (!container) return
  const containerRect = container.getBoundingClientRect()
  const asideEl = (e.currentTarget as HTMLElement).closest('aside') as HTMLElement
  const left = e.clientX - containerRect.left - dragOffsetX
  const top = e.clientY - containerRect.top - dragOffsetY
  // 경계 안에 가두기
  const maxLeft = containerRect.width - asideEl.offsetWidth
  const maxTop = containerRect.height - asideEl.offsetHeight
  pos.value.left = Math.max(0, Math.min(maxLeft, left))
  pos.value.top = Math.max(0, Math.min(maxTop, top))
}
function onDragEnd(e: PointerEvent) {
  dragging.value = false
  ;(e.currentTarget as HTMLElement).releasePointerCapture?.(e.pointerId)
}

onMounted(() => {
  document.addEventListener('mousedown', onDocClick)
  window.addEventListener('keydown', onShortcut)
  // 기본 위치를 좌측 하단으로 (캔버스 영역 높이에 맞춰)
  nextTick(() => {
    const aside = asideRef.value
    const parent = aside?.parentElement
    if (aside && parent) {
      pos.value = {
        left: 12,
        top: Math.max(12, parent.clientHeight - aside.clientHeight - 12),
      }
    }
  })
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick)
  window.removeEventListener('keydown', onShortcut)
})
</script>

<template>
  <aside
    ref="asideRef"
    class="absolute w-10 bg-towa-surface/95 backdrop-blur rounded-lg border border-towa-border shadow-lg shadow-black/40 flex flex-col items-stretch z-30 select-none"
    :style="{ left: `${pos.left}px`, top: `${pos.top}px` }"
  >
    <!-- AI 단일 버튼 + 드롭다운 -->
    <div ref="aiButtonRef" class="relative">
      <button
        class="w-full h-9 flex items-center justify-center rounded-t-lg transition-colors"
        :class="aiMenuOpen
          ? 'bg-towa-accent text-white'
          : 'text-towa-accent hover:bg-towa-accent/15'"
        :disabled="aiLoading !== null || !activeDocument"
        title="AI 도구"
        @click="toggleAiMenu"
      >
        <Sparkles :size="16" :class="{ 'animate-pulse': aiLoading !== null }" />
      </button>
      <!-- 드롭다운 메뉴 (우측으로 펼침) -->
      <div
        v-if="aiMenuOpen"
        class="absolute left-full top-0 ml-1 min-w-[140px] bg-towa-surface border border-towa-border rounded-md shadow-xl shadow-black/40 py-1 z-40"
      >
        <button
          v-for="a in AI_ACTIONS"
          :key="a.id"
          class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-towa-text hover:bg-towa-accent/20 hover:text-towa-accent transition-colors text-left"
          :disabled="aiLoading !== null"
          @click="selectAi(a.id)"
        >
          <component :is="a.icon" :size="14" />
          <span>{{ a.label }}</span>
          <span v-if="aiLoading === a.id" class="ml-auto text-towa-accent text-[10px]">···</span>
        </button>
      </div>
    </div>

    <!-- 구분선 -->
    <div class="mx-1.5 border-t border-towa-border/60" />

    <!-- 일반 도구 -->
    <div class="flex flex-col items-stretch py-1">
      <button
        v-for="t in visibleTools"
        :key="t.type"
        class="w-full h-8 flex items-center justify-center transition-colors"
        :class="activeTool === t.type
          ? 'bg-towa-accent text-white'
          : 'text-towa-text-muted hover:text-towa-text hover:bg-towa-surface-light'"
        :title="`${t.label} [${t.shortcut}]`"
        :disabled="!activeDocument"
        @click="selectTool(t)"
      >
        <component :is="t.icon" :size="15" />
      </button>
    </div>

    <!-- 구분선 -->
    <div class="mx-1.5 border-t border-towa-border/60" />

    <!-- FG/BG 색 — 포토샵 스타일 (큰 사각형 2개가 대각선으로 50% 겹침) -->
    <div class="relative h-9 mx-auto my-2 w-9">
      <!-- BG (뒤, 우하단) -->
      <div
        class="absolute right-0 bottom-0 w-[22px] h-[22px] border-2 border-towa-text/80 cursor-pointer"
        :style="{ backgroundColor }"
        title="배경색 (Alt+드래그로 캔버스 색 추출)"
      />
      <!-- FG (앞, 좌상단) -->
      <div
        class="absolute left-0 top-0 w-[22px] h-[22px] border-2 border-towa-text/80 cursor-pointer shadow-[2px_2px_0_rgba(0,0,0,0.4)]"
        :style="{ backgroundColor: activeColor }"
        title="전경색"
      />
      <!-- swap 화살표 (우상단 살짝 튀어나옴) -->
      <button
        class="absolute -right-1 -top-1 w-3.5 h-3.5 flex items-center justify-center text-towa-text-muted hover:text-towa-accent"
        title="전경/배경 스왑 [X]"
        @click="swapColors"
      >
        <ArrowLeftRight :size="10" />
      </button>
    </div>

    <!-- 하단 drag 핸들 -->
    <button
      class="w-full h-5 flex items-center justify-center rounded-b-lg text-towa-text-muted/60 hover:text-towa-accent transition-colors cursor-grab active:cursor-grabbing"
      :class="{ 'cursor-grabbing': dragging }"
      title="툴바 이동"
      @pointerdown="onDragStart"
      @pointermove="onDragMove"
      @pointerup="onDragEnd"
      @pointercancel="onDragEnd"
    >
      <GripHorizontal :size="12" />
    </button>
  </aside>
</template>
