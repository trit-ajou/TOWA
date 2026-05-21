<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { Loader2 } from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  visible: boolean
  delay?: number
}>(), { delay: 100 })

const shown = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

function clear() {
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
}

watch(() => props.visible, (v) => {
  clear()
  if (v) {
    timer = setTimeout(() => { shown.value = true }, props.delay)
  } else {
    shown.value = false
  }
}, { immediate: true })

onBeforeUnmount(clear)
</script>

<template>
  <Teleport to="body">
    <Transition name="towa-fade">
      <div
        v-if="shown"
        class="fixed inset-0 z-40 flex items-center justify-center bg-black/40 backdrop-blur-sm pointer-events-none"
        aria-live="polite"
        aria-busy="true"
      >
        <div class="flex items-center gap-2 px-4 py-2 rounded-lg bg-towa-surface/90 border border-towa-border shadow-lg text-towa-text">
          <Loader2 :size="18" class="animate-spin text-towa-accent" />
          <span class="text-sm">페이지 불러오는 중...</span>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.towa-fade-enter-active,
.towa-fade-leave-active {
  transition: opacity 0.15s ease;
}
.towa-fade-enter-from,
.towa-fade-leave-to {
  opacity: 0;
}
</style>
