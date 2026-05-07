<script setup lang="ts">
import { ref, computed } from 'vue'
import { useStore } from 'vuex'
import { ScanText, Eraser, Languages, ZoomIn, ZoomOut, Columns2, Square } from 'lucide-vue-next'
import BaseButton from '@/components/common/BaseButton.vue'
import { useAppBackend } from '@/composables/useAppBackend'
import { DEPLOYMENT_MODE } from '@/config/deployment'
import { BackendError } from '@/backend/errors'
import type { AiJobCreateInput, AiJobSnapshot, AiOperationKind } from '@/backend/contracts'

const store = useStore()
const backend = useAppBackend()
const loading = ref<string | null>(null)
const lastResult = ref<{ op: string; status: string; jobId: string } | null>(null)

const zoomLevel = computed(() => store.getters['editor/zoomLevel'])
const viewMode = computed(() => store.getters['editor/canvasViewMode'])
const projectId = computed(() => store.getters['editor/currentProjectId'] as string | null)
const selectedPageId = computed(() => store.getters['editor/selectedPageId'] as string | null)

function buildInput(operationKind: AiOperationKind): AiJobCreateInput {
  const proj = projectId.value ?? 'no-project'
  const page = selectedPageId.value ?? 'no-page'
  const attempt = Date.now()
  const mode = DEPLOYMENT_MODE.value === 'cloud' ? 'saas' : 'local'
  return {
    schemaVersion: 'v1',
    idempotencyKey: `project:${proj}:page:${page}:op:${operationKind}:v:${attempt}`,
    operationKind,
    requestRef: `project/${proj}/page/${page}`,
    document: {
      id: `doc_${page}`,
      name: `page-${page}`,
    },
    artifacts: {},
    runtimeContext: {
      mode,
      workspace_uri: `workspace://project/${proj}/page/${page}`,
      requested_by: 'ui-engine-test',
    },
  }
}

async function pollUntilTerminal(jobId: string, sessionKey: string | null): Promise<AiJobSnapshot> {
  const opts = sessionKey ? { sessionKey } : undefined
  for (let i = 0; i < 60; i++) {
    const snap = await backend.aiJobs.getJob(jobId, opts)
    if (snap.status === 'succeeded' || snap.status === 'failed' || snap.status === 'partial') {
      return snap
    }
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error(`polling timed out for job ${jobId}`)
}

async function runAction(action: AiOperationKind) {
  if (loading.value !== null) return
  loading.value = action
  lastResult.value = null
  try {
    const input = buildInput(action)
    const sessionKey = (store.state as { auth?: { sessionKey: string | null } }).auth?.sessionKey ?? null
    const opts = sessionKey ? { sessionKey } : undefined
    const created = await backend.aiJobs.createJob(input, opts)
    const final = await pollUntilTerminal(created.jobId, sessionKey)
    lastResult.value = { op: action, status: final.status, jobId: final.jobId }
    console.log(`[AiToolbar] ${action} →`, final)
    if (sessionKey) {
      void store.dispatch('auth/refreshCredit')
    }
  } catch (e) {
    const msg = e instanceof BackendError
      ? `${e.payload.code}: ${e.payload.message}`
      : e instanceof Error
        ? e.message
        : String(e)
    lastResult.value = { op: action, status: `error: ${msg}`, jobId: '' }
    console.error(`[AiToolbar] ${action} failed:`, e)
    const sessionKey = (store.state as { auth?: { sessionKey: string | null } }).auth?.sessionKey ?? null
    if (sessionKey) {
      void store.dispatch('auth/refreshCredit')
    }
  } finally {
    loading.value = null
  }
}

function zoomIn() {
  store.commit('editor/SET_ZOOM', zoomLevel.value + 25)
}
function zoomOut() {
  store.commit('editor/SET_ZOOM', zoomLevel.value - 25)
}
function setViewMode(mode: 'single-split' | 'spread') {
  store.commit('editor/SET_CANVAS_VIEW_MODE', mode)
}

const actions: { id: AiOperationKind; label: string; icon: typeof ScanText }[] = [
  { id: 'detect', label: '텍스트 검출', icon: ScanText },
  { id: 'inpaint', label: '인페인팅', icon: Eraser },
  { id: 'translate', label: '번역', icon: Languages },
]
</script>

<template>
  <div class="flex items-center justify-between px-3 py-1.5 bg-towa-surface border-b border-towa-border shrink-0">
    <!-- Left: AI tools -->
    <div class="flex items-center gap-1.5">
      <BaseButton
        v-for="action in actions"
        :key="action.id"
        variant="ghost"
        size="sm"
        :disabled="loading !== null"
        @click="runAction(action.id)"
      >
        <component :is="action.icon" :size="14" :class="{ 'animate-pulse': loading === action.id }" />
        {{ action.label }}
        <span v-if="loading === action.id" class="ml-1 text-[10px] text-towa-accent">처리중...</span>
      </BaseButton>
      <span
        v-if="lastResult"
        class="ml-2 text-[10px] font-mono"
        :class="lastResult.status.startsWith('error') ? 'text-towa-danger' : 'text-towa-text-muted'"
      >
        [{{ lastResult.op }}] {{ lastResult.status }}<span v-if="lastResult.jobId"> ({{ lastResult.jobId.slice(0, 12) }})</span>
      </span>
    </div>

    <!-- Right: view mode + zoom -->
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-1 bg-towa-bg rounded-md p-0.5">
        <button
          class="p-1 rounded transition-colors"
          :class="viewMode === 'single-split' ? 'bg-towa-surface-light text-towa-text' : 'text-towa-text-muted hover:text-towa-text'"
          title="한쪽보기"
          @click="setViewMode('single-split')"
        >
          <Columns2 :size="14" />
        </button>
        <button
          class="p-1 rounded transition-colors"
          :class="viewMode === 'spread' ? 'bg-towa-surface-light text-towa-text' : 'text-towa-text-muted hover:text-towa-text'"
          title="두쪽보기"
          @click="setViewMode('spread')"
        >
          <Square :size="14" />
        </button>
      </div>

      <div class="flex items-center gap-1">
        <button class="p-1 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-text transition-colors" @click="zoomOut">
          <ZoomOut :size="14" />
        </button>
        <span class="text-xs text-towa-text-muted w-10 text-center">{{ zoomLevel }}%</span>
        <button class="p-1 rounded hover:bg-towa-surface-light text-towa-text-muted hover:text-towa-text transition-colors" @click="zoomIn">
          <ZoomIn :size="14" />
        </button>
      </div>
    </div>
  </div>
</template>
