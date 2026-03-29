<script setup lang="ts">
import type { Layer } from '@/types/layer'
import { Eye, EyeOff } from 'lucide-vue-next'

defineProps<{
  layers: Layer[]
}>()

defineEmits<{
  toggle: [layerId: string]
}>()
</script>

<template>
  <div class="border-t border-towa-border">
    <div class="px-3 py-2 border-b border-towa-border">
      <h3 class="text-xs font-semibold text-towa-text-muted uppercase tracking-wider">레이어</h3>
    </div>
    <div>
      <div
        v-for="layer in layers"
        :key="layer.id"
        class="flex items-center gap-2 px-3 py-2 hover:bg-towa-surface-light transition-colors"
      >
        <button
          class="text-towa-text-muted hover:text-towa-text transition-colors"
          @click="$emit('toggle', layer.id)"
        >
          <Eye v-if="layer.visible" :size="14" />
          <EyeOff v-else :size="14" class="opacity-50" />
        </button>
        <span class="text-xs text-towa-text">{{ layer.name }}</span>
      </div>
    </div>
  </div>
</template>
