<script setup lang="ts">
// X 버튼을 눌러야 닫히는 에러 다이얼로그 stack. AI 작업 실패 등에서 사용.
// 메시지는 user-select: text로 두어 카피 가능.
import { X, AlertCircle } from 'lucide-vue-next'
import { useErrorDialog } from '@/composables/useErrorDialog'

const { queue, dismiss } = useErrorDialog()
</script>

<template>
  <div class="fixed top-14 right-4 z-50 flex flex-col gap-2 pointer-events-none">
    <div
      v-for="entry in queue"
      :key="entry.id"
      class="pointer-events-auto max-w-md min-w-[280px] bg-towa-surface border border-towa-danger/60 rounded-md shadow-lg shadow-black/50 overflow-hidden"
      role="alert"
    >
      <div class="flex items-start gap-2 px-3 py-2 border-b border-towa-border bg-towa-danger/15">
        <AlertCircle :size="16" class="shrink-0 text-towa-danger mt-0.5" />
        <h3 class="flex-1 text-sm font-semibold text-towa-text select-text">{{ entry.title }}</h3>
        <button
          class="shrink-0 p-0.5 rounded text-towa-text-muted hover:text-towa-text hover:bg-towa-surface-light transition-colors"
          title="닫기"
          @click="dismiss(entry.id)"
        >
          <X :size="14" />
        </button>
      </div>
      <p class="px-3 py-2 text-xs text-towa-text-muted select-text whitespace-pre-wrap break-words">{{ entry.message }}</p>
    </div>
  </div>
</template>
