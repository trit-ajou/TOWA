<script setup lang="ts">
defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
}>()
</script>

<template>
  <button
    class="inline-flex items-center justify-center gap-1.5 font-medium rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    :class="[
      {
        'bg-towa-accent hover:bg-towa-accent-hover text-white': variant === 'primary' || !variant,
        'bg-towa-surface-light hover:bg-towa-border text-towa-text': variant === 'secondary',
        'hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-text': variant === 'ghost',
        'bg-towa-danger hover:bg-towa-danger/80 text-white': variant === 'danger',
      },
      {
        'text-xs px-2 py-1': size === 'sm',
        'text-sm px-3 py-1.5': size === 'md' || !size,
        'text-base px-4 py-2': size === 'lg',
      },
    ]"
    :disabled="disabled"
  >
    <slot />
  </button>
</template>
