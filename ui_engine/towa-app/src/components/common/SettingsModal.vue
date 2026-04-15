<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useStore } from 'vuex'
import { Settings, Monitor, Brain, Palette, User, Bug, LogOut } from 'lucide-vue-next'
import BaseModal from './BaseModal.vue'
import BaseButton from './BaseButton.vue'
import { useDeploymentMode, type ModeTag } from '@/composables/useDeploymentMode'
import { DEPLOYMENT_MODE, setDeploymentMode, type DeploymentMode } from '@/config/deployment'
import { MODEL_ENGINE_URL } from '@/config/engines'

const store = useStore()
const currentTheme = computed(() => store.getters['editor/theme'])
const { filterByMode } = useDeploymentMode()
const currentDeploymentMode = computed(() => DEPLOYMENT_MODE.value)

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  'open-login': []
}>()

const authUser = computed(() => store.state.auth.user)
const authIsLoggedIn = computed(() => store.getters['auth/isLoggedIn'])
const authCreditBalance = computed(() => store.state.auth.creditBalance)

function handleAccountLogout() {
  store.dispatch('auth/logout')
}

function handleOpenLogin() {
  emit('close')
  emit('open-login')
}

type SettingsTab = 'general' | 'model-standalone' | 'model-cloud' | 'appearance' | 'account' | 'debug'

const activeTab = ref<SettingsTab>('general')

const allTabs: { id: SettingsTab; label: string; icon: typeof Settings; mode: ModeTag }[] = [
  { id: 'general', label: '일반', icon: Settings, mode: 'all' },
  { id: 'model-standalone', label: '모델', icon: Brain, mode: 'standalone' },
  { id: 'model-cloud', label: '모델', icon: Brain, mode: 'cloud' },
  { id: 'appearance', label: '외관', icon: Palette, mode: 'all' },
  { id: 'account', label: '계정', icon: User, mode: 'cloud' },
  { id: 'debug', label: '디버그', icon: Bug, mode: 'all' },
]

const tabs = computed(() => filterByMode(allTabs))

// Placeholder settings state
const settings = ref({
  general: {
    language: 'ko',
    autoSave: true,
    autoSaveInterval: 30,
    recentProjectCount: 3,
    defaultSourceLang: 'ja',
    defaultTargetLang: 'ko',
  },
  inference: {
    mode: 'cloud' as 'local' | 'cloud',
    serverUrl: MODEL_ENGINE_URL,
    apiKey: '',
    maxConcurrent: 3,
    timeout: 60,
  },
  appearance: {
    theme: 'dark' as 'dark' | 'light',
    projectHomeLayout: 'horizontal' as 'vertical' | 'horizontal',
    fontSize: 14,
    sidebarWidth: 240,
    showPageNumbers: true,
  },
})

const uiLanguages = [
  { value: 'ko', label: '한국어' },
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' },
]

const transLanguages = [
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
  { value: 'en', label: 'English' },
  { value: 'zh', label: '中文' },
]
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/60" @click="$emit('close')" />
        <div class="relative bg-towa-surface border border-towa-border rounded-lg shadow-2xl w-full max-w-2xl mx-4 flex overflow-hidden" style="height: 480px;">
          <!-- Sidebar tabs -->
          <div class="w-44 bg-towa-bg border-r border-towa-border p-3 flex flex-col gap-1 shrink-0">
            <h2 class="text-sm font-semibold text-towa-text px-2 py-2 mb-1">환경설정</h2>
            <button
              v-for="tab in tabs"
              :key="tab.id"
              class="flex items-center gap-2 px-2.5 py-2 text-sm rounded transition-colors"
              :class="activeTab === tab.id
                ? 'bg-towa-surface-light text-towa-text font-medium'
                : 'text-towa-text-muted hover:text-towa-text hover:bg-towa-surface-light'"
              @click="activeTab = tab.id"
            >
              <component :is="tab.icon" :size="15" />
              {{ tab.label }}
            </button>
          </div>

          <!-- Content -->
          <div class="flex-1 p-6 overflow-y-auto">
            <!-- General -->
            <div v-if="activeTab === 'general'" class="space-y-5">
              <h3 class="text-base font-semibold text-towa-text">일반 설정</h3>

              <div>
                <label class="block text-xs text-towa-text-muted mb-1">UI 언어</label>
                <select v-model="settings.general.language" class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent">
                  <option v-for="lang in uiLanguages" :key="lang.value" :value="lang.value">{{ lang.label }}</option>
                </select>
              </div>

              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs text-towa-text-muted mb-1">기본 원본 언어</label>
                  <select v-model="settings.general.defaultSourceLang" class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent">
                    <option v-for="lang in transLanguages" :key="lang.value" :value="lang.value">{{ lang.label }}</option>
                  </select>
                </div>
                <div>
                  <label class="block text-xs text-towa-text-muted mb-1">기본 번역 언어</label>
                  <select v-model="settings.general.defaultTargetLang" class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent">
                    <option v-for="lang in transLanguages" :key="lang.value" :value="lang.value">{{ lang.label }}</option>
                  </select>
                </div>
              </div>

              <label class="flex items-center gap-2 text-sm text-towa-text cursor-pointer">
                <input v-model="settings.general.autoSave" type="checkbox" class="accent-towa-accent" />
                자동 저장
              </label>

              <div v-if="settings.general.autoSave">
                <label class="block text-xs text-towa-text-muted mb-1">자동 저장 간격 (초)</label>
                <input v-model.number="settings.general.autoSaveInterval" type="number" min="5" max="300" step="5" class="w-24 bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent" />
              </div>

              <div>
                <label class="block text-xs text-towa-text-muted mb-1">최근 프로젝트 표시 개수</label>
                <input v-model.number="settings.general.recentProjectCount" type="number" min="1" max="10" class="w-24 bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent" />
              </div>
            </div>

            <!-- Model (standalone) -->
            <div v-if="activeTab === 'model-standalone'" class="space-y-5">
              <h3 class="text-base font-semibold text-towa-text">모델 설정</h3>

              <div>
                <label class="block text-xs text-towa-text-muted mb-1">서버 주소</label>
                <div class="flex items-center gap-2">
                  <Monitor :size="14" class="text-towa-text-muted shrink-0" />
                  <input v-model="settings.inference.serverUrl" type="text" class="flex-1 bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent" />
                </div>
              </div>

              <div>
                <label class="block text-xs text-towa-text-muted mb-1">API 키</label>
                <input v-model="settings.inference.apiKey" type="password" placeholder="sk-..." class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text placeholder:text-towa-text-muted focus:outline-none focus:border-towa-accent" />
              </div>

              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs text-towa-text-muted mb-1">최대 동시 요청</label>
                  <input v-model.number="settings.inference.maxConcurrent" type="number" min="1" max="10" class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent" />
                </div>
                <div>
                  <label class="block text-xs text-towa-text-muted mb-1">타임아웃 (초)</label>
                  <input v-model.number="settings.inference.timeout" type="number" min="10" max="300" class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent" />
                </div>
              </div>
            </div>

            <!-- Model (cloud) -->
            <div v-if="activeTab === 'model-cloud'" class="space-y-5">
              <h3 class="text-base font-semibold text-towa-text">모델 선택</h3>

              <div>
                <label class="block text-xs text-towa-text-muted mb-1">텍스트 검출 모델</label>
                <select class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent">
                  <option value="standard">Standard (기본)</option>
                  <option value="advanced">Advanced (정밀)</option>
                </select>
              </div>

              <div>
                <label class="block text-xs text-towa-text-muted mb-1">번역 모델</label>
                <select class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent">
                  <option value="base">Base — 빠르고 가벼움</option>
                  <option value="pro">Pro — 고품질 번역</option>
                </select>
              </div>

              <div>
                <label class="block text-xs text-towa-text-muted mb-1">인페인팅 모델</label>
                <select class="w-full bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent">
                  <option value="standard">Standard</option>
                  <option value="hd">HD — 고해상도 복원</option>
                </select>
              </div>

              <div class="p-3 bg-towa-bg rounded-md">
                <div class="text-xs text-towa-text-muted">현재 플랜</div>
                <div class="text-sm text-towa-text font-medium mt-1">Free</div>
                <p class="text-xs text-towa-text-muted mt-1">Pro 모델은 유료 플랜에서 사용 가능합니다.</p>
              </div>
            </div>

            <!-- Appearance -->
            <div v-if="activeTab === 'appearance'" class="space-y-5">
              <h3 class="text-base font-semibold text-towa-text">외관 설정</h3>

              <div>
                <label class="block text-xs text-towa-text-muted mb-1">프로젝트 홈 레이아웃</label>
                <div class="flex gap-3">
                  <label class="flex items-center gap-1.5 text-sm text-towa-text cursor-pointer">
                    <input v-model="settings.appearance.projectHomeLayout" type="radio" value="horizontal" class="accent-towa-accent" />
                    좌우 배치
                  </label>
                  <label class="flex items-center gap-1.5 text-sm text-towa-text cursor-pointer">
                    <input v-model="settings.appearance.projectHomeLayout" type="radio" value="vertical" class="accent-towa-accent" />
                    상하 배치
                  </label>
                </div>
              </div>

              <div>
                <label class="block text-xs text-towa-text-muted mb-1">테마</label>
                <div class="flex gap-3">
                  <label class="flex items-center gap-1.5 text-sm text-towa-text cursor-pointer">
                    <input :checked="currentTheme === 'dark'" type="radio" name="theme" value="dark" class="accent-towa-accent" @change="store.commit('editor/SET_THEME', 'dark')" />
                    다크
                  </label>
                  <label class="flex items-center gap-1.5 text-sm text-towa-text cursor-pointer">
                    <input :checked="currentTheme === 'light'" type="radio" name="theme" value="light" class="accent-towa-accent" @change="store.commit('editor/SET_THEME', 'light')" />
                    라이트
                  </label>
                </div>
              </div>

              <div>
                <label class="block text-xs text-towa-text-muted mb-1">에디터 폰트 크기 (px)</label>
                <input v-model.number="settings.appearance.fontSize" type="number" min="10" max="24" class="w-24 bg-towa-bg border border-towa-border rounded-md px-3 py-2 text-sm text-towa-text focus:outline-none focus:border-towa-accent" />
              </div>

              <label class="flex items-center gap-2 text-sm text-towa-text cursor-pointer">
                <input v-model="settings.appearance.showPageNumbers" type="checkbox" class="accent-towa-accent" />
                페이지 번호 표시
              </label>
            </div>

            <!-- Account (cloud only) -->
            <div v-if="activeTab === 'account'" class="space-y-5">
              <h3 class="text-base font-semibold text-towa-text">계정 설정</h3>

              <!-- 로그인 상태 -->
              <template v-if="authIsLoggedIn && authUser">
                <div class="space-y-3">
                  <div class="p-4 bg-towa-bg rounded-md space-y-2">
                    <div class="flex items-center justify-between">
                      <span class="text-xs text-towa-text-muted">이메일</span>
                      <span class="text-sm text-towa-text">{{ authUser.email }}</span>
                    </div>
                    <div class="flex items-center justify-between">
                      <span class="text-xs text-towa-text-muted">닉네임</span>
                      <span class="text-sm text-towa-text">{{ authUser.nickname }}</span>
                    </div>
                    <div class="flex items-center justify-between">
                      <span class="text-xs text-towa-text-muted">크레딧 잔액</span>
                      <span class="text-sm text-towa-text font-medium">{{ authCreditBalance }}</span>
                    </div>
                  </div>
                  <button
                    class="flex items-center gap-2 text-sm text-towa-danger hover:text-red-400 transition-colors"
                    @click="handleAccountLogout"
                  >
                    <LogOut :size="14" />
                    로그아웃
                  </button>
                </div>
              </template>

              <!-- 미로그인 상태 -->
              <template v-else>
                <p class="text-sm text-towa-text-muted">클라우드 서비스에 로그인해주세요.</p>
                <BaseButton variant="primary" @click="handleOpenLogin">로그인</BaseButton>
              </template>
            </div>


            <!-- Debug -->
            <div v-if="activeTab === 'debug'" class="space-y-5">
              <h3 class="text-base font-semibold text-towa-text">디버그</h3>
              <p class="text-xs text-towa-text-muted">개발 중 전용. 배포 시 제거됩니다.</p>

              <div>
                <label class="block text-xs text-towa-text-muted mb-1">Deployment Mode</label>
                <div class="flex gap-3">
                  <label class="flex items-center gap-1.5 text-sm text-towa-text cursor-pointer">
                    <input :checked="currentDeploymentMode === 'standalone'" type="radio" name="deploy-mode" value="standalone" class="accent-towa-accent" @change="setDeploymentMode('standalone')" />
                    Standalone
                  </label>
                  <label class="flex items-center gap-1.5 text-sm text-towa-text cursor-pointer">
                    <input :checked="currentDeploymentMode === 'cloud'" type="radio" name="deploy-mode" value="cloud" class="accent-towa-accent" @change="setDeploymentMode('cloud')" />
                    Cloud
                  </label>
                </div>
                <p class="text-[10px] text-towa-text-muted mt-1">전환 시 설정 탭 목록이 바로 반영됩니다.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.15s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
