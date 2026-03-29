<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const menuRef = ref<HTMLElement>()

function onClickOutside(e: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) {
    emit('close')
  }
}

onMounted(() => document.addEventListener('click', onClickOutside, true))
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside, true))
</script>

<template>
  <div v-if="open" ref="menuRef" class="absolute right-0 top-full mt-1 w-48 bg-towa-surface border border-towa-border rounded-lg shadow-xl z-50 py-1">
    <slot />
  </div>
</template>
