<script setup lang="ts">
import { ref, watch, onBeforeUnmount, computed } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { useThumbnailUrl } from '@/composables/useThumbnailUrl'

const props = withDefaults(defineProps<{
  visible: boolean
  delay?: number
  /** Page being switched to. When provided, its thumbnail is shown beneath
   *  the spinner so the user gets immediate visual feedback (#39 §점진적 표시). */
  pageId?: string | null
}>(), { delay: 100 })

const shown = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

const incomingPageId = computed(() => (props.visible ? props.pageId ?? null : null))
const { url: thumbUrl } = useThumbnailUrl(incomingPageId)

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
        class="fixed inset-0 z-40 flex items-center justify-center bg-black/60 backdrop-blur-sm pointer-events-none"
        aria-live="polite"
        aria-busy="true"
      >
        <!-- Incoming page's thumbnail as a progressive preview. -->
        <img
          v-if="thumbUrl"
          :src="thumbUrl"
          alt=""
          class="absolute inset-0 m-auto max-h-full max-w-full object-contain opacity-70"
        />
        <div class="relative flex items-center gap-2 px-4 py-2 rounded-lg bg-towa-surface/90 border border-towa-border shadow-lg text-towa-text">
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
