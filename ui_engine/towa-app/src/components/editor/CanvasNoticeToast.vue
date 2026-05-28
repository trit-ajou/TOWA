<script setup lang="ts">
// 캔버스 영역 중앙에 페이드인/아웃되는 안내 토스트. 메시지는 useCanvasNotice singleton에서 옴.
// 표시 자체는 v-if + Transition으로 200ms 페이드 처리.
import { useCanvasNotice } from '@/composables/useCanvasNotice'

const { message } = useCanvasNotice()
</script>

<template>
  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="opacity-0 scale-95"
    enter-to-class="opacity-100 scale-100"
    leave-active-class="transition duration-300 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="message"
      class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-30 px-4 py-3 rounded-lg bg-towa-surface/95 border border-towa-border shadow-xl shadow-black/50 backdrop-blur-sm pointer-events-none text-center"
      role="status"
      aria-live="polite"
    >
      <span class="text-sm text-towa-text">{{ message }}</span>
    </div>
  </Transition>
</template>
