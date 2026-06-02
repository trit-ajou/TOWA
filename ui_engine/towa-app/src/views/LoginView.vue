<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useStore } from 'vuex'
import { useRouter, useRoute } from 'vue-router'
import { ArrowRight, ScanText, Eraser, Languages, Brush } from 'lucide-vue-next'

const store = useStore()
const router = useRouter()
const route = useRoute()

const email = ref('')
const nickname = ref('')

const authError = computed(() => store.state.auth.error)
const isLoading = computed(() => store.state.auth.isLoading)
const isLoggedIn = computed<boolean>(() => store.getters['auth/isLoggedIn'])

const redirectTarget = computed(() => {
  const r = route.query.redirect
  return typeof r === 'string' && r.startsWith('/') ? r : '/library'
})

// When the global 401 handler redirects here, surface a clear message so the
// user knows why they were bounced. (#39 §401 분기)
const sessionExpired = computed(() => route.query.expired === '1')

onMounted(() => {
  if (isLoggedIn.value) {
    router.replace(redirectTarget.value)
  }
})

async function submit() {
  if (!email.value.trim()) return
  try {
    await store.dispatch('auth/devLogin', {
      email: email.value.trim(),
      nickname: nickname.value.trim() || undefined,
    })
    // Server state is now driven by TanStack Query. The auth/SET_SESSION
    // subscription in main.ts wires the new user namespace; the cross-cutting
    // invalidate-on-login (#39 §sync) lives there too. No imperative load
    // needed here.
    router.replace(redirectTarget.value)
  } catch {
    // store가 error 관리
  }
}
</script>

<template>
  <div class="font-korean min-h-[calc(100vh-48px)] grid grid-cols-1 lg:grid-cols-2">
    <!-- ===== LEFT: branding / atmosphere ===== -->
    <aside class="relative hidden lg:flex bg-towa-surface border-r-2 border-towa-text overflow-hidden">
      <!-- Halftone backdrop -->
      <div class="absolute inset-0 bg-halftone opacity-50 pointer-events-none" />
      <div class="absolute inset-0 bg-grain pointer-events-none" />

      <!-- Diagonal hatch accent -->
      <div
        class="absolute -top-16 -left-16 w-[360px] h-[160px] bg-hatch opacity-50 -rotate-12 pointer-events-none"
      />

      <!-- Content -->
      <div class="relative z-10 flex flex-col justify-between w-full p-10 xl:p-14">
        <!-- Top: tag -->
        <div class="anim-fade">
          <div class="inline-flex items-center gap-2">
            <span class="h-px w-10 bg-towa-pink" />
            <span class="text-[11px] tracking-[0.3em] text-towa-text-muted uppercase font-display font-medium">
              Translator's Workstation
            </span>
          </div>
        </div>

        <!-- Middle: big title -->
        <div>
          <h2
            class="font-display font-bold leading-[0.95] tracking-tight text-towa-text mb-6 anim-rise delay-1"
            style="font-size: clamp(2.75rem, 5vw, 4.5rem)"
          >
            돌아오신 걸<br />
            <span class="marker">환영합니다.</span>
          </h2>
          <p class="text-sm text-towa-text-muted max-w-sm leading-relaxed anim-rise delay-2">
            저장된 프로젝트, 진행 중이던 페이지,
            그리고 다음 작업까지 — 로그인 후 라이브러리에서 이어서 진행할 수 있습니다.
          </p>

          <!-- Mini workflow ticker -->
          <div class="mt-10 grid grid-cols-4 gap-3 anim-rise delay-3 max-w-md">
            <div
              v-for="item in [
                { label: '검출', icon: ScanText, color: '#9569B4' },
                { label: '지움', icon: Eraser, color: '#e84a8a' },
                { label: '번역', icon: Languages, color: '#fb8b24' },
                { label: '식자', icon: Brush, color: '#4ade80' },
              ]"
              :key="item.label"
              class="flex flex-col items-center text-center gap-2 p-3 bg-towa-bg"
              style="border: 2px solid var(--towa-border)"
            >
              <component :is="item.icon" :size="18" :style="{ color: item.color }" />
              <span class="text-[10px] tracking-[0.2em] uppercase font-display text-towa-text-muted">
                {{ item.label }}
              </span>
            </div>
          </div>
        </div>

        <!-- Bottom: footer mark -->
        <div class="text-[10px] tracking-[0.3em] text-towa-text-muted uppercase font-display anim-fade delay-5">
          TOWA · One-stop Workstation
        </div>
      </div>

      <!-- Big watermark -->
      <div
        aria-hidden="true"
        class="absolute -bottom-10 right-[-2rem] pointer-events-none anim-fade delay-4"
      >
        <span
          class="font-display font-bold tracking-tight select-none"
          style="
            font-size: clamp(8rem, 18vw, 16rem);
            line-height: 1;
            color: transparent;
            -webkit-text-stroke: 1px rgba(232, 74, 138, 0.15);
          "
        >
          T<br />W<br />A
        </span>
      </div>
    </aside>

    <!-- ===== RIGHT: form ===== -->
    <main class="relative flex items-center justify-center p-6 sm:p-10 bg-towa-bg">
      <!-- subtle halftone -->
      <div class="absolute inset-0 bg-halftone opacity-30 pointer-events-none" />

      <div class="relative w-full max-w-md anim-rise delay-2">
        <!-- Header -->
        <div class="mb-10">
          <div class="text-[11px] tracking-[0.3em] text-towa-accent uppercase font-display font-medium mb-3">
            Sign in
          </div>
          <h1 class="font-display font-bold text-towa-text leading-tight" style="font-size: clamp(2rem, 4vw, 2.75rem)">
            로그인
          </h1>
          <p class="text-xs text-towa-text-muted mt-2">
            현재 개발용 임시 로그인 — 이메일과 닉네임만 입력하면 진입할 수 있습니다.
          </p>
        </div>

        <!-- Form -->
        <form class="space-y-5" @submit.prevent="submit">
          <div>
            <label class="block text-[11px] tracking-[0.2em] text-towa-text-muted uppercase font-display font-medium mb-2">
              이메일
            </label>
            <input
              v-model="email"
              type="email"
              autofocus
              autocomplete="email"
              placeholder="user@example.com"
              class="w-full bg-transparent border-0 border-b-2 border-towa-border px-0 py-3 text-base text-towa-text placeholder:text-towa-text-muted/60 focus:outline-none focus:border-towa-accent transition-colors font-korean"
            />
          </div>

          <div>
            <label class="block text-[11px] tracking-[0.2em] text-towa-text-muted uppercase font-display font-medium mb-2">
              닉네임 <span class="text-towa-text-muted/60 lowercase">(선택)</span>
            </label>
            <input
              v-model="nickname"
              type="text"
              autocomplete="nickname"
              placeholder="tester"
              class="w-full bg-transparent border-0 border-b-2 border-towa-border px-0 py-3 text-base text-towa-text placeholder:text-towa-text-muted/60 focus:outline-none focus:border-towa-accent transition-colors font-korean"
            />
          </div>

          <label class="flex items-center gap-2 text-xs text-towa-text-muted cursor-pointer select-none pt-2">
            <input type="checkbox" class="accent-towa-accent" />
            로그인 상태 유지
          </label>

          <!-- Session-expired notice (from a 401 redirect) -->
          <div
            v-if="sessionExpired && !authError"
            class="px-3 py-2 bg-towa-warning/10 text-sm text-towa-text"
            style="border: 2px solid var(--towa-warning)"
          >
            세션이 만료되어 로그인이 필요합니다. 다시 로그인해주세요.
          </div>

          <!-- Error -->
          <div
            v-if="authError"
            class="px-3 py-2 bg-towa-danger/10 text-sm text-towa-danger"
            style="border: 2px solid var(--towa-danger)"
          >
            {{ authError.message }}
          </div>

          <!-- Submit -->
          <button
            type="submit"
            :disabled="!email.trim() || isLoading"
            class="group w-full inline-flex items-center justify-center gap-3 bg-towa-accent hover:bg-towa-accent-hover transition-colors px-5 py-4 text-white font-display font-medium disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            style="border: 2px solid var(--towa-text); box-shadow: 5px 5px 0 0 var(--towa-text)"
          >
            <span>{{ isLoading ? '로그인 중...' : '로그인' }}</span>
            <ArrowRight v-if="!isLoading" :size="18" class="transition-transform group-hover:translate-x-1" />
          </button>
        </form>

        <!-- Divider -->
        <div class="my-8 flex items-center gap-3 text-[10px] tracking-[0.3em] uppercase font-display text-towa-text-muted">
          <span class="h-px flex-1 bg-towa-border" />
          또는
          <span class="h-px flex-1 bg-towa-border" />
        </div>

        <!-- Signup placeholder -->
        <div class="text-center text-sm text-towa-text-muted">
          아직 계정이 없으신가요?
          <button
            type="button"
            class="ml-1 text-towa-pink hover:text-towa-pink/80 underline underline-offset-4 decoration-2 cursor-not-allowed opacity-70"
            disabled
            title="추후 정식 회원가입 예정"
          >
            회원가입 (준비 중)
          </button>
        </div>

        <!-- Back link -->
        <div class="mt-10 text-center">
          <button
            type="button"
            class="text-xs text-towa-text-muted hover:text-towa-text transition-colors"
            @click="router.push('/')"
          >
            ← 메인으로 돌아가기
          </button>
        </div>
      </div>
    </main>
  </div>
</template>
