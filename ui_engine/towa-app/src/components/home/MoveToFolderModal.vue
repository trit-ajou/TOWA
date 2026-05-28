<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { Home } from 'lucide-vue-next'
import BaseButton from '@/components/common/BaseButton.vue'
import BaseModal from '@/components/common/BaseModal.vue'
import FolderPickerNode from '@/components/home/FolderPickerNode.vue'
import type { FolderNode } from '@/types/folder'

const props = defineProps<{
  open: boolean
  /** 현재 위치 (이동 메뉴를 띄운 항목의 현재 folderId). 비교용. */
  currentFolderId: string | null
  /** 이동 대상 항목 표시명 (모달 본문에 노출). */
  itemName: string
  /**
   * Disabled set — 이 폴더 id에는 이동 불가 (예: 자기 자신, 자기 후손).
   * 폴더 이동 시 cycle 차단용. 프로젝트 이동에는 보통 빈 set.
   */
  disabledIds?: Set<string>
}>()

const emit = defineEmits<{
  close: []
  submit: [folderId: string | null]
}>()

const store = useStore()
const tree = computed<FolderNode[]>(() => store.getters['folders/tree'])

const expanded = ref<Set<string>>(new Set())
function toggle(id: string) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

const selected = ref<string | null>(null)
watch(() => props.open, (v) => {
  if (v) selected.value = props.currentFolderId
})

function isDisabled(id: string): boolean {
  return props.disabledIds?.has(id) ?? false
}

function pick(id: string | null) {
  if (id != null && isDisabled(id)) return
  selected.value = id
}

function submit() {
  if (selected.value === props.currentFolderId) return
  if (selected.value != null && isDisabled(selected.value)) return
  emit('submit', selected.value)
}

const canSubmit = computed(() =>
  selected.value !== props.currentFolderId &&
  !(selected.value != null && isDisabled(selected.value)),
)
</script>

<template>
  <BaseModal :open="open" title="폴더로 이동" @close="emit('close')">
    <p class="text-sm text-towa-text-muted mb-3">
      <span class="font-medium text-towa-text">{{ itemName }}</span>
      을(를) 어디로 옮길까요?
    </p>

    <div class="bg-towa-surface-light border border-towa-border rounded p-2 max-h-72 overflow-y-auto text-sm">
      <!-- Root option -->
      <button
        class="w-full text-left px-2 py-1.5 rounded flex items-center gap-1.5"
        :class="selected === null
          ? 'bg-towa-accent/15 text-towa-accent'
          : 'text-towa-text-muted hover:text-towa-text hover:bg-towa-surface'"
        @click="pick(null)"
      >
        <Home :size="14" />
        루트 (전체)
      </button>

      <!-- Folder tree -->
      <FolderPickerNode
        v-for="f in tree"
        :key="f.id"
        :folder="f"
        :expanded="expanded"
        :selected-id="selected"
        :disabled-ids="disabledIds"
        :level="0"
        @toggle="toggle"
        @pick="pick"
      />
    </div>

    <template #footer>
      <BaseButton variant="secondary" size="sm" @click="emit('close')">취소</BaseButton>
      <BaseButton variant="primary" size="sm" :disabled="!canSubmit" @click="submit">이동</BaseButton>
    </template>
  </BaseModal>
</template>
