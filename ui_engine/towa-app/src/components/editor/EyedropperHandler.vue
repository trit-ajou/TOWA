<script setup lang="ts">
// Alt+클릭으로 캔버스에서 배경색을 추출. 도구를 EYEDROPPER로 명시적으로 전환할 필요 없이
// 어떤 도구를 쓰고 있더라도 Alt 모디파이어가 눌려있으면 스포이드처럼 동작 (포토샵 패턴).
// 추출된 색은 전경색이 아니라 배경색(editor/backgroundColor)에 set — spec(canvas_ui_specs.md).
import { onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { getCanvasInstance } from '@bitmappery/services/canvas-service'

const store = useStore()

function rgbaToHex(r: number, g: number, b: number): string {
  const h = (n: number) => n.toString(16).padStart(2, '0')
  return `#${h(r)}${h(g)}${h(b)}`
}

function onClick(e: MouseEvent) {
  if (!e.altKey) return
  if (e.button !== 0) return
  const area = document.getElementById('towa-canvas-area')
  if (!area || !area.contains(e.target as Node)) return

  const canvas = getCanvasInstance() as unknown as { getElement(): HTMLCanvasElement } | null
  const el = canvas?.getElement?.()
  if (!el) return

  const rect = el.getBoundingClientRect()
  if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) {
    return
  }
  // CSS 좌표 → canvas internal pixel 좌표 (HiDPI / zoom 보정)
  const x = Math.floor(((e.clientX - rect.left) / rect.width) * el.width)
  const y = Math.floor(((e.clientY - rect.top) / rect.height) * el.height)
  const ctx = el.getContext('2d')
  if (!ctx) return
  try {
    const data = ctx.getImageData(x, y, 1, 1).data
    const hex = rgbaToHex(data[0], data[1], data[2])
    store.commit('editor/SET_BACKGROUND_COLOR', hex)
    // bitmappery interaction-pane이 같은 클릭을 사용하지 않도록 가로채기.
    e.preventDefault()
    e.stopPropagation()
  } catch {
    // tainted canvas 등 예외는 무시.
  }
}

onMounted(() => document.addEventListener('click', onClick, true))
onBeforeUnmount(() => document.removeEventListener('click', onClick, true))
</script>

<template><div style="display: none" /></template>
