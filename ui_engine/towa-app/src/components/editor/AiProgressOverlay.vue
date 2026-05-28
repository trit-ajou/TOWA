<script setup lang="ts">
// AI 작업이 도는 동안 캔버스 우상단에 spinner + 작업명을 띄워 사용자에게 진행 중임을 알림.
// 현재 정책: 캔버스 입력은 잠그지 않음 (다른 페이지 탐색 등은 자유). 같은 페이지에서
// 텍스트 편집 시 결과 적용 단계의 머지 정책은 별도 이슈로 다룸.
import { computed } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { useAiActions } from '@/composables/useAiActions'
import type { AiOperationKind } from '@/backend/contracts'

const { loading } = useAiActions()

const LABELS: Record<AiOperationKind, string> = {
  detect: '텍스트 검출 중',
  inpaint: '인페인팅 중',
  translate: '번역 중',
  pipeline: 'AI 파이프라인 실행 중',
}

const label = computed(() => (loading.value ? LABELS[loading.value] : ''))
</script>

<template>
  <Transition
    enter-active-class="transition duration-150 ease-out"
    enter-from-class="opacity-0 -translate-y-1"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="loading"
      class="absolute top-3 right-3 z-30 flex items-center gap-2 px-3 py-2 rounded-md bg-towa-surface/95 border border-towa-accent/40 shadow-lg shadow-black/40 backdrop-blur-sm pointer-events-none"
      role="status"
      aria-live="polite"
    >
      <Loader2 :size="16" class="text-towa-accent animate-spin" />
      <span class="text-xs text-towa-text">{{ label }}</span>
    </div>
  </Transition>
</template>
