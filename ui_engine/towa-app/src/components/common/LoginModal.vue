<script setup lang="ts">
import { ref, computed } from 'vue'
import { useStore } from 'vuex'
import BaseModal from './BaseModal.vue'
import BaseButton from './BaseButton.vue'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  login: []
}>()

const store = useStore()
const email = ref('')
const password = ref('')

const authError = computed(() => store.state.auth.error)
const isLoading = computed(() => store.state.auth.isLoading)

async function submit() {
  if (!email.value.trim() || !password.value) return
  try {
    await store.dispatch('auth/login', {
      email: email.value.trim(),
      password: password.value,
    })
    emit('login')
    emit('close')
  } catch {
    // error state는 store가 관리, 템플릿에서 노출
  }
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
          autocomplete="current-password"
          class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text placeholder:text-towa-text-muted focus:outline-none focus:border-towa-accent"
          @keyup.enter="submit"
        />
      </div>
      <div class="flex items-center">
        <label class="flex items-center gap-2 text-xs text-towa-text-muted cursor-pointer">
          <input type="checkbox" class="accent-towa-accent" />
          로그인 상태 유지
        </label>
      </div>

      <!-- Error display -->
      <div
        v-if="authError"
        class="p-3 bg-red-500/10 border border-red-500/30 rounded-md text-sm text-red-400"
      >
        {{ authError.message }}
      </div>
    </div>

    <template #footer>
      <BaseButton variant="secondary" @click="emit('close')">취소</BaseButton>
      <BaseButton
        variant="primary"
        :disabled="!email.trim() || !password || isLoading"
        @click="submit"
      >
        {{ isLoading ? '로그인 중...' : '로그인' }}
      </BaseButton>
    </template>
  </BaseModal>
</template>
