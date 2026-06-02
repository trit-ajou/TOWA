<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Folder, Image, Trash2, RotateCcw, ChevronLeft } from 'lucide-vue-next'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import { useModal } from '@/composables/useModal'
import { useTrash } from '@/composables/useTrash'
import type { TrashEntry } from '@/file-adapter/contracts'

const router = useRouter()
const trashApi = useTrash()

const items = trashApi.all
const isLoading = trashApi.isLoading

const confirmModal = useModal()
const pendingAction = ref<null | { kind: 'restore' | 'permanent'; entry: TrashEntry }>(null)
const actionError = ref<string | null>(null)

function askRestore(entry: TrashEntry) {
  pendingAction.value = { kind: 'restore', entry }
  actionError.value = null
  confirmModal.open()
}
function askPermanent(entry: TrashEntry) {
  pendingAction.value = { kind: 'permanent', entry }
  actionError.value = null
  confirmModal.open()
}

async function confirmAction() {
  if (!pendingAction.value) return
  const { kind, entry } = pendingAction.value
  try {
    if (kind === 'restore') {
      if (entry.type === 'folder') await trashApi.restoreFolder(entry.item.id)
      else await trashApi.restoreProject(entry.item.id)
    } else {
      if (entry.type === 'folder') await trashApi.permanentlyDeleteFolder(entry.item.id)
      else await trashApi.permanentlyDeleteProject(entry.item.id)
    }
    confirmModal.close()
    pendingAction.value = null
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : '실패'
  }
}

function back() {
  router.push('/library')
}

function fmtDate(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function entryName(entry: TrashEntry): string {
  return entry.item.name
}
</script>

<template>
  <div class="h-[calc(100vh-48px)] overflow-y-auto p-6">
    <div class="flex items-center gap-3 mb-6">
      <button class="p-1.5 text-towa-text-muted hover:text-towa-text rounded transition-colors" @click="back">
        <ChevronLeft :size="18" />
      </button>
      <h1 class="text-xl font-semibold flex items-center gap-2">
        <Trash2 :size="18" /> 휴지통
      </h1>
    </div>

    <p v-if="isLoading" class="text-sm text-towa-text-muted">불러오는 중...</p>
    <p v-else-if="items.length === 0" class="text-sm text-towa-text-muted">휴지통이 비어 있습니다.</p>

    <ul v-else class="space-y-1">
      <li
        v-for="entry in items"
        :key="`${entry.type}-${entry.item.id}`"
        class="flex items-center gap-3 px-3 py-2 bg-towa-surface rounded-lg hover:bg-towa-surface-light transition-colors"
      >
        <Folder v-if="entry.type === 'folder'" :size="18" class="text-towa-text-muted shrink-0" />
        <Image v-else :size="18" class="text-towa-text-muted shrink-0" />

        <div class="flex-1 min-w-0">
          <div class="text-sm text-towa-text truncate">{{ entryName(entry) }}</div>
          <div class="text-[10px] text-towa-text-muted">
            {{ entry.type === 'folder' ? '폴더' : '프로젝트' }} ·
            삭제 {{ fmtDate(entry.item.deletedAt) }}
          </div>
        </div>

        <button
          class="p-1.5 text-towa-text-muted hover:text-towa-accent rounded transition-colors"
          title="복구"
          @click="askRestore(entry)"
        >
          <RotateCcw :size="16" />
        </button>
        <button
          class="p-1.5 text-towa-text-muted hover:text-red-400 rounded transition-colors"
          title="영구 삭제"
          @click="askPermanent(entry)"
        >
          <Trash2 :size="16" />
        </button>
      </li>
    </ul>

    <BaseModal :open="confirmModal.isOpen.value" :title="pendingAction?.kind === 'restore' ? '복구' : '영구 삭제'" @close="confirmModal.close()">
      <p class="text-sm text-towa-text-muted">
        <template v-if="pendingAction?.kind === 'restore'">
          <span class="font-medium text-towa-text">{{ pendingAction && entryName(pendingAction.entry) }}</span>
          을(를) 복구합니다.
        </template>
        <template v-else>
          <span class="font-medium text-towa-text">{{ pendingAction && entryName(pendingAction.entry) }}</span>
          을(를) 영구 삭제합니다. 이 작업은 되돌릴 수 없습니다.
        </template>
      </p>
      <p v-if="actionError" class="text-xs text-red-400 mt-2">{{ actionError }}</p>
      <template #footer>
        <BaseButton variant="secondary" size="sm" @click="confirmModal.close()">취소</BaseButton>
        <BaseButton
          :variant="pendingAction?.kind === 'restore' ? 'primary' : 'danger'"
          size="sm"
          @click="confirmAction"
        >
          {{ pendingAction?.kind === 'restore' ? '복구' : '영구 삭제' }}
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>
