<script setup lang="ts">
import { ref } from 'vue'
import BaseModal from './BaseModal.vue'
import BaseButton from './BaseButton.vue'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  login: []
}>()

const email = ref('')
const password = ref('')

function submit() {
  if (!email.value.trim() || !password.value) return
  emit('login')
}
</script>

<template>
  <BaseModal title="로그인" :open="open" @close="emit('close')">
    <div class="space-y-4">
      <div>
        <label class="block text-xs text-towa-text-muted mb-1">이메일</label>
        <input
          v-model="email"
          type="email"
          placeholder="user@example.com"
          class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text placeholder:text-towa-text-muted focus:outline-none focus:border-towa-accent"
          @keyup.enter="submit"
        />
      </div>
      <div>
        <label class="block text-xs text-towa-text-muted mb-1">비밀번호</label>
        <input
          v-model="password"
          type="password"
          placeholder="••••••••"
          class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text placeholder:text-towa-text-muted focus:outline-none focus:border-towa-accent"
          @keyup.enter="submit"
        />
      </div>
      <div class="flex items-center justify-between">
        <label class="flex items-center gap-2 text-xs text-towa-text-muted cursor-pointer">
          <input type="checkbox" class="accent-towa-accent" />
          로그인 상태 유지
        </label>
        <button class="text-xs text-towa-accent hover:underline">비밀번호 찾기</button>
      </div>
    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="emit('close')">취소</BaseButton>
      <BaseButton variant="primary" :disabled="!email.trim() || !password" @click="submit">로그인</BaseButton>
    </template>
  </BaseModal>
</template>
