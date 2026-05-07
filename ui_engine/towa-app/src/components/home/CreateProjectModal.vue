<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { Upload, X, FileImage } from 'lucide-vue-next'
import BaseModal from '@/components/common/BaseModal.vue'
import BaseButton from '@/components/common/BaseButton.vue'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  create: [form: typeof formData & { files: File[] }]
}>()

const formData = reactive({
  name: '',
  sourceLang: 'ja',
  targetLang: 'ko',
  autoDetect: true,
  autoInpaint: true,
  autoTranslate: false,
  inferenceMode: 'cloud' as 'local' | 'cloud',
})

const files = ref<File[]>([])
const isDragging = ref(false)
const fileInput = ref<HTMLInputElement>()

const sortedFiles = computed(() =>
  [...files.value].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
)

const languages = [
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
  { value: 'en', label: 'English' },
  { value: 'zh', label: '中文' },
]

function addFiles(newFiles: FileList | null) {
  if (!newFiles) return
  const imageFiles = Array.from(newFiles).filter((f) => f.type.startsWith('image/'))
  const existing = new Set(files.value.map((f) => f.name))
  files.value.push(...imageFiles.filter((f) => !existing.has(f.name)))
}

function removeFile(index: number) {
  const sorted = sortedFiles.value
  const target = sorted[index]
  files.value = files.value.filter((f) => f !== target)
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  addFiles(e.dataTransfer?.files ?? null)
}

function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  addFiles(input.files)
  input.value = ''
}

function submit() {
  if (!formData.name.trim()) return
  emit('create', { ...formData, files: sortedFiles.value })
  formData.name = ''
  files.value = []
}
</script>

<template>
  <BaseModal title="새 프로젝트" :open="open" @close="emit('close')">
    <div class="space-y-4">
      <div>
        <label class="block text-xs text-towa-text-muted mb-1">프로젝트 이름</label>
        <input
          v-model="formData.name"
          type="text"
          placeholder="예: 원피스 1081화"
          class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text placeholder:text-towa-text-muted focus:outline-none focus:border-towa-accent"
          @keyup.enter="submit"
        />
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-xs text-towa-text-muted mb-1">원본 언어</label>
          <select
            v-model="formData.sourceLang"
            class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent"
          >
            <option v-for="lang in languages" :key="lang.value" :value="lang.value">{{ lang.label }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-towa-text-muted mb-1">번역 언어</label>
          <select
            v-model="formData.targetLang"
            class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent"
          >
            <option v-for="lang in languages" :key="lang.value" :value="lang.value">{{ lang.label }}</option>
          </select>
        </div>
      </div>

      <!-- File upload -->
      <div>
        <label class="block text-xs text-towa-text-muted mb-1">페이지 이미지</label>
        <div
          class="border-2 border-dashed rounded-lg p-4 text-center transition-colors cursor-pointer"
          :class="isDragging ? 'border-towa-accent bg-towa-accent/5' : 'border-towa-border hover:border-towa-text-muted'"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="onDrop"
          @click="fileInput?.click()"
        >
          <Upload :size="24" class="mx-auto mb-2 text-towa-text-muted" />
          <p class="text-sm text-towa-text-muted">
            이미지를 드래그하거나 클릭하여 선택
          </p>
          <p class="text-xs text-towa-text-muted/60 mt-1">파일명 순으로 자동 정렬됩니다</p>
          <input
            ref="fileInput"
            type="file"
            multiple
            accept="image/*"
            class="hidden"
            @change="onFileSelect"
          />
        </div>

        <div v-if="sortedFiles.length > 0" class="mt-2 max-h-32 overflow-y-auto space-y-1">
          <div
            v-for="(file, i) in sortedFiles"
            :key="file.name"
            class="flex items-center gap-2 px-2 py-1 rounded bg-towa-bg text-xs"
          >
            <FileImage :size="12" class="text-towa-text-muted shrink-0" />
            <span class="text-towa-text-muted w-5 text-right shrink-0">{{ i + 1 }}</span>
            <span class="text-towa-text truncate flex-1">{{ file.name }}</span>
            <button class="text-towa-text-muted hover:text-towa-danger shrink-0" @click.stop="removeFile(i)">
              <X :size="12" />
            </button>
          </div>
        </div>
      </div>

      <div>
        <label class="block text-xs text-towa-text-muted mb-2">초벌번역 설정</label>
        <div class="space-y-2">
          <label class="flex items-center gap-2 text-sm text-towa-text cursor-pointer">
            <input v-model="formData.autoDetect" type="checkbox" class="accent-towa-accent" />
            자동 텍스트 검출
          </label>
          <label class="flex items-center gap-2 text-sm text-towa-text cursor-pointer">
            <input v-model="formData.autoInpaint" type="checkbox" class="accent-towa-accent" />
            자동 인페인팅
          </label>
          <label class="flex items-center gap-2 text-sm text-towa-text cursor-pointer">
            <input v-model="formData.autoTranslate" type="checkbox" class="accent-towa-accent" />
            자동 번역
          </label>
        </div>
      </div>

    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="emit('close')">취소</BaseButton>
      <BaseButton variant="primary" :disabled="!formData.name.trim()" @click="submit">
        생성{{ sortedFiles.length > 0 ? ` (${sortedFiles.length}p)` : '' }}
      </BaseButton>
    </template>
  </BaseModal>
</template>
