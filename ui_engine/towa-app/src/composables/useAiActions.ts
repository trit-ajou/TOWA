import { computed, ref } from 'vue'
import { useStore } from 'vuex'
import { useAppBackend } from '@/composables/useAppBackend'
import { usePageLoader } from '@/composables/usePageLoader'
import { DEPLOYMENT_MODE } from '@/config/deployment'
import { BackendError } from '@/backend/errors'
import type { AiJobCreateInput, AiJobSnapshot, AiOperationKind } from '@/backend/contracts'
import type { Page, PageStatus } from '@/types/page'
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

export function useAiActions() {
  const store = useStore()
  const backend = useAppBackend()
  const { savePage } = usePageLoader()
  const loading = ref<AiOperationKind | null>(null)
  const lastResult = ref<AiActionResult | null>(null)

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
      store.commit('pages/UPDATE_PAGE', { ...pageRecord, status: 'ai-processing' satisfies PageStatus })
      restorePreviousPage = true

      const input = await buildInput(action)
      const sessionKey = (store.state as { auth?: { sessionKey: string | null } }).auth?.sessionKey ?? null
      const opts = sessionKey ? { sessionKey } : undefined
      const created = await backend.aiJobs.createJob(input, opts)
      const final = await pollUntilTerminal(created.jobId, sessionKey)
      if (final.status === 'succeeded') {
        const applied = await applyAiJobSnapshotToCurrentPage({
          store,
          backend: backend.aiJobs,
          snapshot: final,
          projectId: proj,
          pageId,
          savePage,
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
    const pageRecord = store.getters['pages/byId'](proj, pageId) as Page | undefined
    if (!pageRecord) throw new Error(`Page ${pageId} is not loaded`)
    return pageRecord
  }
  function restorePage(pageRecord: Page | null): void {
    if (pageRecord) store.commit('pages/UPDATE_PAGE', pageRecord)
  }
  function currentUserEmail(): string | null {
    const state = store.state as { auth?: { user?: { email?: string } | null } }
    return state.auth?.user?.email ?? null
  }

  return { loading, lastResult, runAction }
}
