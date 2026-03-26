<script setup lang="ts">
import { Search } from 'lucide-vue-next'

const model = defineModel<string>({ default: '' })

defineProps<{
  placeholder?: string
}>()
</script>

<template>
  <div class="relative">
    <Search :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-towa-text-muted" />
    <input
      v-model="model"
      type="text"
      :placeholder="placeholder ?? '검색...'"
      class="w-full bg-towa-bg border border-towa-border rounded-md pl-9 pr-3 py-2 text-sm text-towa-text placeholder:text-towa-text-muted focus:outline-none focus:border-towa-accent transition-colors"
    />
  </div>
</template>
