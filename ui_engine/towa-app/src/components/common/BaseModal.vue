<script setup lang="ts">
import { X } from 'lucide-vue-next'

defineProps<{
  title: string
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

function onBackdrop() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center"
      >
        <div class="absolute inset-0 bg-black/60" @click="onBackdrop" />
        <div class="relative bg-towa-surface border border-towa-border rounded-lg shadow-2xl w-full max-w-md mx-4">
          <div class="flex items-center justify-between px-5 py-4 border-b border-towa-border">
            <h2 class="text-lg font-semibold text-towa-text">{{ title }}</h2>
            <button
              class="p-1 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-text transition-colors"
              @click="emit('close')"
            >
              <X :size="18" />
            </button>
          </div>
          <div class="px-5 py-4">
            <slot />
          </div>
          <div v-if="$slots.footer" class="px-5 py-3 border-t border-towa-border flex justify-end gap-2">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.15s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
