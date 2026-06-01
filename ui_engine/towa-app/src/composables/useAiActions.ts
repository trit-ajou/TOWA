import { computed, ref } from 'vue'
import { useStore } from 'vuex'
import { useQueryClient } from '@tanstack/vue-query'
import { useAppBackend } from '@/composables/useAppBackend'
import { useAutoSave } from '@/composables/useAutoSave'
import { useFileAdapter } from '@/composables/useFileAdapter'
import { useErrorDialog } from '@/composables/useErrorDialog'
import { queryKeys } from '@/composables/queryKeys'
import { DEPLOYMENT_MODE } from '@/config/deployment'
import { BackendError } from '@/backend/errors'
import type { AiJobCreateInput, AiJobSnapshot, AiOperationKind } from '@/backend/contracts'
import type { Page, PageStatus } from '@/types/page'
import type { PageSummary } from '@/file-adapter'
import { applyAiJobSnapshotToCurrentPage } from '@/ai/result-applier'
import { getTextMeta, isTextLayer } from '@/utils/text-layer'
import type { Layer } from '@bitmappery/definitions/document'
// @ts-expect-error bitmappery JS module
import { createSyncSnapshot } from '@bitmappery/utils/document-util'
// @ts-expect-error bitmappery JS module
import { canvasToBlob, resizeImage } from '@bitmappery/utils/canvas-util'

export interface AiActionResult {
  op: string
  status: string
  jobId: string
}

// AI 진행 상태는 module-scope singleton. 여러 컴포넌트(toolbox + 진행 알림 오버레이)가
// 같은 상태를 구독해야 하므로 useAiActions() 호출마다 새 ref를 만들면 안 됨.
const loading = ref<AiOperationKind | null>(null)
const lastResult = ref<AiActionResult | null>(null)

export function useAiActions() {
  const store = useStore()
  const backend = useAppBackend()
  const qc = useQueryClient()
  const fileAdapter = useFileAdapter()
  const { markDirty, saveImmediately } = useAutoSave()
  const { showError } = useErrorDialog()

  function patchPageInCache(proj: string, pageId: string, patch: Partial<PageSummary>) {
    qc.setQueryData<PageSummary[]>(queryKeys.pages.byProject(proj), (old) => {
      if (!old) return old
      return old.map((p) => (p.id === pageId ? { ...p, ...patch } : p))
    })
  }

  const projectId = computed(() => store.getters['editor/currentProjectId'] as string | null)
  const selectedPageId = computed(() => store.getters['editor/selectedPageId'] as string | null)

  async function buildInput(operationKind: AiOperationKind): Promise<AiJobCreateInput> {
    const proj = projectId.value ?? 'no-project'
    const page = selectedPageId.value ?? 'no-page'
    const attempt = Date.now()
    const mode = DEPLOYMENT_MODE.value === 'cloud' ? 'saas' : 'local'
    const activeDocument = store.getters['bmp/activeDocument']
    if (!activeDocument) {
      throw new Error('No active Bitmappery document is loaded')
    }
    const snapshot = createSyncSnapshot(activeDocument)
    const normalizedSnapshot = await resizeImage(snapshot, activeDocument.width, activeDocument.height)
    const primaryBitmap = await canvasToBlob(normalizedSnapshot, 'image/png')
    const requestedBy = currentUserEmail() ?? 'ui-engine'
    const textLayers: Layer[] = (activeDocument.layers ?? []).filter(isTextLayer)
    return {
      schemaVersion: 'v1',
      idempotencyKey: `project:${proj}:page:${page}:op:${operationKind}:v:${attempt}`,
      operationKind,
      requestRef: `project/${proj}/page/${page}`,
      document: {
        id: `doc_${page}`,
        name: `page-${page}`,
        width: activeDocument.width,
        height: activeDocument.height,
        layers: [
          {
            id: 'layer_primary_bitmap',
            name: 'Visible page bitmap',
            type: 'graphic',
            left: 0,
            top: 0,
            width: activeDocument.width,
            height: activeDocument.height,
            source_ref: 'artifact://input/primary_bitmap',
          },
        ],
        text_blocks: textLayers.map((layer) => {
          const meta = getTextMeta(layer)
          return {
            block_id: meta?.blockId ?? layer.id,
            source_lang_text: meta?.original ?? '',
            translated_text: layer.text.value,
            bbox: { x: layer.left, y: layer.top, width: layer.width, height: layer.height },
          }
        }),
        stage_meta: {},
      },
      primaryBitmap,
      runtimeContext: {
        mode,
        workspace_uri: `workspace://project/${proj}/page/${page}`,
        requested_by: requestedBy,
        target_regions: [],
        selected_layer_ids: [],
      },
    }
  }

  async function pollUntilTerminal(jobId: string, sessionKey: string | null): Promise<AiJobSnapshot> {
    const opts = sessionKey ? { sessionKey } : undefined
    for (let i = 0; i < 300; i++) {
      const snap = await backend.aiJobs.getJob(jobId, opts)
      if (snap.status === 'succeeded' || snap.status === 'failed' || snap.status === 'partial') {
        return snap
      }
      await new Promise((r) => setTimeout(r, 1000))
    }
    throw new Error(`polling timed out for job ${jobId}`)
  }

  async function runAction(action: AiOperationKind) {
    if (loading.value !== null) return
    loading.value = action
    lastResult.value = null
    let previousPage: Page | null = null
    let restorePreviousPage = false
    try {
      const proj = requireProjectId()
      const pageId = requirePageId()
      const pageRecord = requireCurrentPage(proj, pageId)
      previousPage = { ...pageRecord }
      patchPageInCache(proj, pageId, { status: 'ai-processing' satisfies PageStatus })
      restorePreviousPage = true

      const input = await buildInput(action)
      const sessionKey = (store.state as { auth?: { sessionKey: string | null } }).auth?.sessionKey ?? null
      const opts = sessionKey ? { sessionKey } : undefined
      const created = await backend.aiJobs.createJob(input, opts)
      const final = await pollUntilTerminal(created.jobId, sessionKey)
      if (final.status === 'succeeded') {
        const applied = await applyAiJobSnapshotToCurrentPage({
          store,
          queryClient: qc,
          backend: backend.aiJobs,
          fileAdapter,
          snapshot: final,
          projectId: proj,
          pageId,
          markDirty,
          saveImmediately,
          onBackgroundApplied: (index) => {
            store.commit('bmp/showNotification', {
              title: 'AI 작업 완료',
              message: `${index}페이지의 AI ${action} 결과가 적용되었습니다.`,
            })
          },
          sessionKey,
        })
        restorePreviousPage = false
        lastResult.value = {
          op: action,
          status: `${final.status}: +${applied.textLayerCount} text, +${applied.graphicLayerCount} image`,
          jobId: final.jobId,
        }
      } else {
        restorePage(previousPage)
        restorePreviousPage = false
        const reason = final.error?.message ? `: ${final.error.message}` : ''
        lastResult.value = { op: action, status: `${final.status}${reason}`, jobId: final.jobId }
        // 실패/부분 성공도 사용자가 진행 상황을 알 수 있게 dismissible 다이얼로그로 노출.
        // bitmappery notification(5초 자동 닫힘 + truncate)은 카피·정독에 부적합.
        showError(
          `AI ${action} ${final.status === 'failed' ? '실패' : '부분 성공'}`,
          final.error?.message ?? `상태: ${final.status} (jobId: ${final.jobId})`,
        )
      }
      console.log(`[AI] ${action} →`, final)
    } catch (e) {
      if (restorePreviousPage) {
        restorePage(previousPage)
      }
      const msg = e instanceof BackendError
        ? `${e.payload.code}: ${e.payload.message}`
        : e instanceof Error
          ? e.message
          : String(e)
      lastResult.value = { op: action, status: `error: ${msg}`, jobId: '' }
      console.error(`[AI] ${action} failed:`, e)
      showError(`AI ${action} 오류`, msg)
    } finally {
      const sessionKey = (store.state as { auth?: { sessionKey: string | null } }).auth?.sessionKey ?? null
      if (sessionKey) {
        void store.dispatch('auth/refreshCredit')
      }
      loading.value = null
    }
  }

  function requireProjectId(): string {
    if (!projectId.value) throw new Error('No project is selected')
    return projectId.value
  }
  function requirePageId(): string {
    if (!selectedPageId.value) throw new Error('No page is selected')
    return selectedPageId.value
  }
  function requireCurrentPage(proj: string, pageId: string): Page {
    const list = qc.getQueryData<PageSummary[]>(queryKeys.pages.byProject(proj)) ?? []
    const summary = list.find((p) => p.id === pageId)
    if (!summary) throw new Error(`Page ${pageId} is not loaded`)
    return { id: summary.id, projectId: summary.projectId, index: summary.index, status: summary.status }
  }
  function restorePage(pageRecord: Page | null): void {
    if (pageRecord) patchPageInCache(pageRecord.projectId, pageRecord.id, { status: pageRecord.status })
  }
  function currentUserEmail(): string | null {
    const state = store.state as { auth?: { user?: { email?: string } | null } }
    return state.auth?.user?.email ?? null
  }

  return { loading, lastResult, runAction }
}
