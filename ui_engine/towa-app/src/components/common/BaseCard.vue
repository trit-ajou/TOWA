<script setup lang="ts">
defineProps<{
  hoverable?: boolean
}>()
</script>

<template>
  <div
    class="bg-towa-surface border border-towa-border rounded-lg overflow-hidden transition-all"
    :class="{
      'hover:border-towa-accent/50 hover:shadow-lg hover:shadow-towa-accent/5 cursor-pointer': hoverable,
    }"
  >
    <slot />
  </div>
</template>
