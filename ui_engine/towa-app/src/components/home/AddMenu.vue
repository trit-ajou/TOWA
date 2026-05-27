<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { Plus, FilePlus, FolderPlus } from 'lucide-vue-next'
import BaseCard from '@/components/common/BaseCard.vue'

// --- Module-level single-open state ---
// Multiple AddMenu instances share this; only one popover can be open at a time.
type OwnerId = symbol
const openOwner = ref<OwnerId | null>(null)
const popX = ref(0)
const popY = ref(0)
let docListenerInstalled = false

function installDocListener() {
  if (docListenerInstalled) return
  docListenerInstalled = true
  window.addEventListener('click', (ev) => {
    if (openOwner.value == null) return
    const target = ev.target as HTMLElement | null
    // Keep the popover open if the click landed on either the trigger or the popover itself.
    if (target?.closest('[data-add-menu-trigger]')) return
    if (target?.closest('[data-add-menu-popover]')) return
    openOwner.value = null
  })
}
installDocListener()

const emit = defineEmits<{
  createProject: []
  createFolder: []
}>()

defineProps<{
  variant?: 'icon-button' | 'tile' | 'toolbar'
  label?: string
}>()

const myId: OwnerId = Symbol('add-menu')
const open = computed(() => openOwner.value === myId)

function openAtEvent(ev: MouseEvent) {
  popX.value = ev.clientX
  popY.value = ev.clientY
  openOwner.value = myId
}

function openAtElement(ev: Event) {
  const el = ev.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  popX.value = rect.right
  popY.value = rect.bottom + 4
  openOwner.value = myId
}

function close() { openOwner.value = null }

function pick(action: 'createProject' | 'createFolder') {
  close()
  emit(action)
}

onBeforeUnmount(() => {
  if (open.value) close()
})
</script>

<template>
  <!-- Tile: matches FolderCard/ProjectCard size, single + glyph -->
  <BaseCard
    v-if="variant === 'tile'"
    hoverable
    data-add-menu-trigger
    @click="openAtEvent($event)"
  >
    <div class="aspect-[3/4] flex items-center justify-center text-towa-text-muted hover:text-towa-accent transition-colors">
      <Plus :size="40" />
    </div>
    <div class="px-3 py-2">
      <h3 class="text-sm font-medium text-towa-text-muted">{{ label ?? '추가' }}</h3>
    </div>
  </BaseCard>

  <!-- Toolbar: pill button -->
  <button
    v-else-if="variant === 'toolbar'"
    data-add-menu-trigger
    class="flex items-center gap-1 px-3 py-1.5 rounded-md bg-towa-accent text-white text-sm font-medium hover:bg-towa-accent-hover transition-colors"
    @click="openAtElement($event)"
  >
    <Plus :size="14" />
    <span>{{ label ?? '추가' }}</span>
  </button>

  <!-- icon-button (sidebar): small + -->
  <button
    v-else
    data-add-menu-trigger
    class="p-1 text-towa-text-muted hover:text-towa-accent rounded transition-colors"
    :title="label ?? '추가'"
    @click="openAtElement($event)"
  >
    <Plus :size="14" />
  </button>

  <!-- Popover, teleported to body -->
  <Teleport to="body">
    <div
      v-if="open"
      data-add-menu-popover
      class="fixed bg-towa-surface-light border border-towa-border rounded shadow-lg py-1 text-xs z-50 min-w-[140px]"
      :style="{ left: popX + 'px', top: popY + 'px', transform: 'translate(-50%, 4px)' }"
    >
      <button
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-towa-text-muted hover:text-towa-text flex items-center gap-1.5"
        @click="pick('createProject')"
      >
        <FilePlus :size="12" /> 새 프로젝트
      </button>
      <button
        class="w-full text-left px-3 py-1.5 hover:bg-towa-surface text-towa-text-muted hover:text-towa-text flex items-center gap-1.5"
        @click="pick('createFolder')"
      >
        <FolderPlus :size="12" /> 새 폴더
      </button>
    </div>
  </Teleport>
</template>
