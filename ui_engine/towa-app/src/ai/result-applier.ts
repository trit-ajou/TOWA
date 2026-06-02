import type { Store } from 'vuex'
import type { QueryClient } from '@tanstack/vue-query'

import type { AiJobSnapshot, AiJobsBackend, TransportPatchOperation } from '@/backend/contracts'
import type { FileAdapter, PageSummary } from '@/file-adapter'
import type { LayerTextMeta, TextPolygon, WritingMode } from '@/types/text-block'
import { queryKeys } from '@/composables/queryKeys'
import { thumbnailCache } from '@/file-adapter/cache-instances'
// @ts-expect-error bitmappery JS module
import DocumentFactory from '@bitmappery/factories/document-factory'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'
import type { Document, Layer } from '@bitmappery/definitions/document'
import { LayerTypes } from '@bitmappery/definitions/layer-types'
// @ts-expect-error bitmappery JS module
import { blobToCanvas, canvasToBlob } from '@bitmappery/utils/canvas-util'
// @ts-expect-error bitmappery JS module
import { createSyncSnapshot } from '@bitmappery/utils/document-util'

const AI_TEXT_FONT = 'Noto Sans KR'
const AI_TEXT_SIZE = 24
const AI_TEXT_COLOR = '#000000'

export interface ApplyAiJobSnapshotOptions {
  store: Store<unknown>
  queryClient: QueryClient
  backend: Pick<AiJobsBackend, 'getArtifact'>
  fileAdapter: FileAdapter
  snapshot: AiJobSnapshot
  projectId: string
  pageId: string
  /** Mark the autosave state dirty for the page (active-path only). */
  markDirty: () => void
  /** Drive the autosave doSave + dirty-reset (active-path only). */
  saveImmediately: (pageId?: string) => Promise<void>
  /** Optional toast hook for the background path. */
  onBackgroundApplied?: (pageIndex: number) => void
  sessionKey?: string | null
  appliedAt?: Date
}

export interface ApplyAiJobSnapshotResult {
  applied: boolean
  reason?: string
  textLayerCount: number
  graphicLayerCount: number
  appliedMode?: 'active' | 'background'
}

interface BitmapArtifactPatch {
  artifactRef: string
  layerPayload?: Record<string, unknown>
}

interface AiLayerSet {
  textLayers: Layer[]
  graphicLayers: Layer[]
  replaceTextLayers: boolean
}

export async function applyAiJobSnapshotToCurrentPage(
  options: ApplyAiJobSnapshotOptions,
): Promise<ApplyAiJobSnapshotResult> {
  if (options.snapshot.status !== 'succeeded') {
    return {
      applied: false,
      reason: 'status_not_succeeded',
      textLayerCount: 0,
      graphicLayerCount: 0,
    }
  }

  const summaries = options.queryClient.getQueryData<PageSummary[]>(
    queryKeys.pages.byProject(options.projectId),
  ) ?? []
  const page = summaries.find((p) => p.id === options.pageId)
  if (!page) {
    throw new Error(`Cannot apply AI result: page not found (${options.pageId})`)
  }

  // The AI job may have outlived the user's stay on the originating page.
  // When activeDocument no longer points at our pageId, applying mutations to
  // store would corrupt whatever document is now active. Take the background
  // path instead: fetch the original snapshot, mutate a detached document
  // object, and PUT it back without touching bitmappery's store.
  const editorState = (options.store.state as { editor?: { selectedPageId?: string | null } }).editor
  const onActivePage = editorState?.selectedPageId === options.pageId

  // translate 응답은 detect와 같은 `replace_text_blocks` 패치로 도착하지만 의도가
  // 다르다 (TRANSLATE_REST_CONTRACT: geometry 보존, translated_text만 채움).
  // 응답 op 이름이 아니라 요청 시 operationKind로 분기해야 detect용 로직(텍스트
  // layer 정리·재생성)이 translate 응답에 잘못 적용되어 사용자가 옮긴 박스가
  // 사라지거나 새 박스가 덧붙는 현상을 막을 수 있다.
  if (options.snapshot.operationKind === 'translate') {
    return onActivePage
      ? applyTranslateOnActive(options, page)
      : applyTranslateInBackground(options, page)
  }

  if (onActivePage) {
    return applyOnActive(options, page)
  }
  return applyInBackground(options, page)
}

async function applyOnActive(
  options: ApplyAiJobSnapshotOptions,
  page: PageSummary,
): Promise<ApplyAiJobSnapshotResult> {
  const operationLabel = toOperationLabel(options.snapshot.operationKind)
  const timestamp = formatLayerTimestamp(options.appliedAt ?? new Date())
  const docForSize = options.store.getters['bmp/activeDocument'] as { width?: number; height?: number } | undefined
  const docW = docForSize?.width ?? 800
  const docH = docForSize?.height ?? 1200

  const layerSet = buildTextLayers(options.snapshot.documentPatch.patches, operationLabel, timestamp, docW, docH)
  const graphicLayers = await fetchAndBuildGraphicLayers(options, docW, docH, operationLabel, timestamp)

  if (layerSet.replaceTextLayers) {
    const activeDocument = options.store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
    const currentLayers = activeDocument?.layers ?? []
    for (let i = currentLayers.length - 1; i >= 0; i--) {
      if (currentLayers[i].type === LayerTypes.LAYER_TEXT) {
        options.store.commit('bmp/removeLayer', i)
      }
    }
  }

  for (const layer of layerSet.textLayers) {
    options.store.commit('bmp/addLayer', layer)
  }
  // 텍스트 레이어가 항상 최상단(배열 끝)에 오도록 graphic은 첫 텍스트 직전에 insert.
  // bmp/addLayer는 무조건 push라서 그대로 부르면 graphic이 텍스트 위로 올라가 가린다.
  for (const layer of graphicLayers) {
    const doc = options.store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
    const layers = doc?.layers ?? []
    const firstTextIdx = layers.findIndex((l) => l.type === LayerTypes.LAYER_TEXT)
    if (firstTextIdx === -1) {
      options.store.commit('bmp/addLayer', layer)
    } else {
      options.store.commit('bmp/insertLayerAtIndex', { index: firstTextIdx, layer })
    }
  }

  options.queryClient.setQueryData<PageSummary[]>(
    queryKeys.pages.byProject(options.projectId),
    (old) => {
      if (!old) return old
      return old.map((p) => (p.id === options.pageId ? { ...p, status: 'in-progress' } : p))
    },
  )

  // None of bmp/addLayer | bmp/insertLayerAtIndex | bmp/removeLayer push to
  // bitmappery history, so useAutoSave's saveState subscriber doesn't fire.
  // We mark dirty explicitly so the save below goes through doSave (which
  // resets dirty) and so a failure leaves the dirty flag set for the next
  // autosave attempt instead of silently dropping the AI result.
  options.markDirty()
  await options.saveImmediately(options.pageId)

  void page
  return {
    applied: true,
    appliedMode: 'active',
    textLayerCount: layerSet.textLayers.length,
    graphicLayerCount: graphicLayers.length,
  }
}

async function applyInBackground(
  options: ApplyAiJobSnapshotOptions,
  page: PageSummary,
): Promise<ApplyAiJobSnapshotResult> {
  // 1) Pull the latest snapshot from the server. We don't trust the in-memory
  //    pageBinaryCache here because the user may have edited and saved the
  //    page from a different session, and `originalImage`/`thumbnail` aren't
  //    cached on the client at all — they live behind getPageSnapshot.
  const snapshot = await options.fileAdapter.getPageSnapshot(options.pageId)
  if (!snapshot) {
    return {
      applied: false,
      reason: 'page_snapshot_missing',
      textLayerCount: 0,
      graphicLayerCount: 0,
      appliedMode: 'background',
    }
  }

  const doc = (await DocumentFactory.fromBlob(snapshot.layerBlob)) as Document
  const docW = doc.width
  const docH = doc.height

  const operationLabel = toOperationLabel(options.snapshot.operationKind)
  const timestamp = formatLayerTimestamp(options.appliedAt ?? new Date())
  const layerSet = buildTextLayers(options.snapshot.documentPatch.patches, operationLabel, timestamp, docW, docH)
  const graphicLayers = await fetchAndBuildGraphicLayers(options, docW, docH, operationLabel, timestamp)

  // 2) Mutate the detached document — no store mutations, so the user's
  //    current active page is untouched.
  if (layerSet.replaceTextLayers) {
    doc.layers = doc.layers.filter((l) => l.type !== LayerTypes.LAYER_TEXT)
  }

  // Graphic layers go just below the first text layer (same invariant as the
  // active path: text on top of inpaint output).
  for (const layer of graphicLayers) {
    const firstTextIdx = doc.layers.findIndex((l) => l.type === LayerTypes.LAYER_TEXT)
    if (firstTextIdx === -1) {
      doc.layers.push(layer)
    } else {
      doc.layers.splice(firstTextIdx, 0, layer)
    }
  }
  for (const layer of layerSet.textLayers) {
    doc.layers.push(layer)
  }

  // 3) Capture a fresh thumbnail off the detached document without touching
  //    the active zCanvas. createSyncSnapshot renders to an offscreen canvas.
  const composedCanvas = createSyncSnapshot(doc) as HTMLCanvasElement
  const maxW = 200
  const maxH = 300
  const scale = Math.min(maxW / composedCanvas.width, maxH / composedCanvas.height, 1)
  const tw = Math.max(1, Math.round(composedCanvas.width * scale))
  const th = Math.max(1, Math.round(composedCanvas.height * scale))
  const thumbCanvas = document.createElement('canvas')
  thumbCanvas.width = tw
  thumbCanvas.height = th
  const tctx = thumbCanvas.getContext('2d')
  if (tctx) tctx.drawImage(composedCanvas, 0, 0, tw, th)
  const thumbnail = await canvasToBlob(thumbCanvas, 'image/png')

  // 4) PUT directly. Bypass usePageLoader.savePage because that one reads
  //    activeDocument, which is some other page right now.
  const layerBlob = (await DocumentFactory.toBlob(doc)) as Blob
  await options.fileAdapter.savePageSnapshot({
    page: {
      id: page.id,
      projectId: page.projectId,
      index: page.index,
      status: 'in-progress',
    },
    originalImage: snapshot.originalImage,
    layerBlob,
    thumbnail,
  })

  // 5) Keep the consumer caches in sync (thumbnail + page status) so any UI
  //    showing this page's card refreshes immediately.
  await thumbnailCache.set(page.id, thumbnail)
  options.queryClient.setQueryData(queryKeys.binary.thumbnail(page.id), thumbnail)
  options.queryClient.setQueryData<PageSummary[]>(
    queryKeys.pages.byProject(options.projectId),
    (old) => {
      if (!old) return old
      return old.map((p) => (p.id === options.pageId ? { ...p, status: 'in-progress' } : p))
    },
  )
  options.queryClient.invalidateQueries({ queryKey: queryKeys.pages.byProject(options.projectId) })

  options.onBackgroundApplied?.(page.index)

  return {
    applied: true,
    appliedMode: 'background',
    textLayerCount: layerSet.textLayers.length,
    graphicLayerCount: graphicLayers.length,
  }
}

// --- translate apply paths ---------------------------------------------------

interface TranslateBlockUpdate {
  translated: string
}

function buildTranslateUpdates(patches: TransportPatchOperation[]): Map<string, TranslateBlockUpdate> {
  const updates = new Map<string, TranslateBlockUpdate>()
  for (const patch of patches) {
    if (patch.op !== 'replace_text_blocks' && patch.op !== 'append_text_blocks') continue
    for (const raw of textBlocksFromPatch(patch)) {
      if (!isRecord(raw)) continue
      const blockId = stringValue(raw.block_id ?? raw.id)
      if (!blockId) continue
      const translated = stringValue(raw.translated_text ?? raw.translated)
      updates.set(blockId, { translated })
    }
  }
  return updates
}

async function applyTranslateOnActive(
  options: ApplyAiJobSnapshotOptions,
  page: PageSummary,
): Promise<ApplyAiJobSnapshotResult> {
  const updates = buildTranslateUpdates(options.snapshot.documentPatch.patches)
  const activeDocument = options.store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
  const layers = activeDocument?.layers ?? []
  let updatedCount = 0
  for (let idx = 0; idx < layers.length; idx++) {
    const layer = layers[idx]
    if (layer.type !== LayerTypes.LAYER_TEXT) continue
    const blockId = (layer.meta as Partial<LayerTextMeta> | undefined)?.blockId
    if (typeof blockId !== 'string' || !updates.has(blockId)) continue
    const update = updates.get(blockId)!
    const nextText = { ...layer.text, value: update.translated }
    const nextMeta = { ...(layer.meta ?? {}), status: 'translated' as const }
    options.store.commit('bmp/updateLayer', { index: idx, opts: { text: nextText, meta: nextMeta } })
    updates.delete(blockId)
    updatedCount++
  }
  if (updates.size > 0) {
    console.warn(`[AI translate] ${updates.size} response blocks did not match any layer`, Array.from(updates.keys()))
  }

  options.queryClient.setQueryData<PageSummary[]>(
    queryKeys.pages.byProject(options.projectId),
    (old) => {
      if (!old) return old
      return old.map((p) => (p.id === options.pageId ? { ...p, status: 'in-progress' } : p))
    },
  )
  options.markDirty()
  await options.saveImmediately(options.pageId)

  void page
  return {
    applied: true,
    appliedMode: 'active',
    textLayerCount: updatedCount,
    graphicLayerCount: 0,
  }
}

async function applyTranslateInBackground(
  options: ApplyAiJobSnapshotOptions,
  page: PageSummary,
): Promise<ApplyAiJobSnapshotResult> {
  const snapshot = await options.fileAdapter.getPageSnapshot(options.pageId)
  if (!snapshot) {
    return {
      applied: false,
      reason: 'page_snapshot_missing',
      textLayerCount: 0,
      graphicLayerCount: 0,
      appliedMode: 'background',
    }
  }

  const doc = (await DocumentFactory.fromBlob(snapshot.layerBlob)) as Document
  const updates = buildTranslateUpdates(options.snapshot.documentPatch.patches)
  let updatedCount = 0
  for (const layer of doc.layers) {
    if (layer.type !== LayerTypes.LAYER_TEXT) continue
    const blockId = (layer.meta as Partial<LayerTextMeta> | undefined)?.blockId
    if (typeof blockId !== 'string' || !updates.has(blockId)) continue
    const update = updates.get(blockId)!
    layer.text = { ...layer.text, value: update.translated }
    layer.meta = { ...(layer.meta ?? {}), status: 'translated' }
    updates.delete(blockId)
    updatedCount++
  }
  if (updates.size > 0) {
    console.warn(`[AI translate bg] ${updates.size} response blocks did not match any layer`, Array.from(updates.keys()))
  }

  const composedCanvas = createSyncSnapshot(doc) as HTMLCanvasElement
  const maxW = 200
  const maxH = 300
  const scale = Math.min(maxW / composedCanvas.width, maxH / composedCanvas.height, 1)
  const tw = Math.max(1, Math.round(composedCanvas.width * scale))
  const th = Math.max(1, Math.round(composedCanvas.height * scale))
  const thumbCanvas = document.createElement('canvas')
  thumbCanvas.width = tw
  thumbCanvas.height = th
  const tctx = thumbCanvas.getContext('2d')
  if (tctx) tctx.drawImage(composedCanvas, 0, 0, tw, th)
  const thumbnail = await canvasToBlob(thumbCanvas, 'image/png')

  const layerBlob = (await DocumentFactory.toBlob(doc)) as Blob
  await options.fileAdapter.savePageSnapshot({
    page: {
      id: page.id,
      projectId: page.projectId,
      index: page.index,
      status: 'in-progress',
    },
    originalImage: snapshot.originalImage,
    layerBlob,
    thumbnail,
  })

  await thumbnailCache.set(page.id, thumbnail)
  options.queryClient.setQueryData(queryKeys.binary.thumbnail(page.id), thumbnail)
  options.queryClient.setQueryData<PageSummary[]>(
    queryKeys.pages.byProject(options.projectId),
    (old) => {
      if (!old) return old
      return old.map((p) => (p.id === options.pageId ? { ...p, status: 'in-progress' } : p))
    },
  )
  options.queryClient.invalidateQueries({ queryKey: queryKeys.pages.byProject(options.projectId) })

  options.onBackgroundApplied?.(page.index)

  return {
    applied: true,
    appliedMode: 'background',
    textLayerCount: updatedCount,
    graphicLayerCount: 0,
  }
}

// --- helpers (shared by both paths) -----------------------------------------

function buildTextLayers(
  patches: TransportPatchOperation[],
  operationLabel: string,
  timestamp: string,
  docW: number,
  docH: number,
): AiLayerSet {
  const textLayers: Layer[] = []
  let replaceTextLayers = false
  for (const patch of patches) {
    if (patch.op !== 'replace_text_blocks' && patch.op !== 'append_text_blocks') continue
    if (patch.op === 'replace_text_blocks') replaceTextLayers = true
    const rawBlocks = textBlocksFromPatch(patch)
    for (const rawBlock of rawBlocks) {
      textLayers.push(createAiTextLayerFromPayload(rawBlock, operationLabel, timestamp, textLayers.length + 1, docW, docH))
    }
  }
  return { textLayers, graphicLayers: [], replaceTextLayers }
}

async function fetchAndBuildGraphicLayers(
  options: ApplyAiJobSnapshotOptions,
  docW: number,
  docH: number,
  operationLabel: string,
  timestamp: string,
): Promise<Layer[]> {
  const graphicLayers: Layer[] = []
  const bitmapArtifactPatches = collectBitmapArtifactPatches(options.snapshot)
  for (const patch of bitmapArtifactPatches) {
    const blob = await options.backend.getArtifact(
      options.snapshot.jobId,
      patch.artifactRef,
      options.sessionKey ? { sessionKey: options.sessionKey } : undefined,
    )
    const canvas = await blobToCanvas(blob)
    // Document와 AI 결과 bitmap 크기가 다르면 좌표계 mismatch로 렌더가 잘리거나 스케일이
    // 어긋남. 이론상 model-engine이 동일 크기로 돌려줘야 하지만 실제로는 모델/리사이즈
    // 정책으로 다를 수 있으므로, 진단용 경고를 남겨 다른 팀이 빠르게 인지하게 한다.
    // (issue #12: inpaint 결과가 잘리는 현상 재현 시 이 메시지가 노출됨)
    if (canvas.width !== docW || canvas.height !== docH) {
      const detail = `document ${docW}x${docH}, AI bitmap ${canvas.width}x${canvas.height} (artifact: ${patch.artifactRef})`
      console.warn(`[AI bitmap size mismatch] ${detail}`)
      options.store.commit('bmp/showNotification', {
        title: 'AI 결과 해상도 불일치',
        message: detail,
      })
    }
    graphicLayers.push(createAiGraphicLayer(canvas, patch.layerPayload, operationLabel, timestamp, graphicLayers.length + 1))
  }
  return graphicLayers
}

function textBlocksFromPatch(patch: TransportPatchOperation): unknown[] {
  return Array.isArray(patch.payload.text_blocks) ? patch.payload.text_blocks : []
}

function createAiTextLayerFromPayload(
  payload: unknown,
  operationLabel: string,
  timestamp: string,
  index: number,
  docW: number,
  docH: number,
): Layer {
  const block = isRecord(payload) ? payload : {}
  const original = stringValue(block.source_lang_text ?? block.original)
  const translated = stringValue(block.translated_text ?? block.translated)
  const bbox = bboxFromPayload(block.bbox)
  const blockId = stringValue(block.block_id ?? block.id) || `ai-block-${index}`
  const polygon = polygonFromPayload(block.polygon)
  const readingOrder = numberOrUndefined(block.reading_order ?? block.readingOrder)
  const writingMode = writingModeFromPayload(block.writing_mode ?? block.writingMode)
  const sourceRegionRef = stringOrUndefined(block.source_region_ref ?? block.sourceRegionRef)
  const meta: LayerTextMeta = {
    blockId,
    original,
    status: translated ? 'translated' : 'detected',
    boxMode: 'fixed',
    ...(polygon ? { polygon } : {}),
    ...(readingOrder !== undefined ? { readingOrder } : {}),
    ...(writingMode ? { writingMode } : {}),
    ...(sourceRegionRef ? { sourceRegionRef } : {}),
  }
  // 박스 = bbox.width/height. document 전체가 아닌 검출된 박스 그대로 보존하여
  // box-mode 렌더에서 정렬 기준으로 사용. document 크기는 박스 clamp용으로만.
  const width = Math.min(Math.max(1, Math.round(bbox.width)), Math.max(1, docW))
  const height = Math.min(Math.max(1, Math.round(bbox.height)), Math.max(1, docH))
  return LayerFactory.create({
    name: aiLayerName(operationLabel, timestamp, index),
    type: LayerTypes.LAYER_TEXT,
    left: bbox.x,
    top: bbox.y,
    width,
    height,
    transparent: true,
    visible: true,
    text: {
      // text.value는 번역문 슬롯. 검출만 끝난 상태에선 빈 값으로 두고,
      // canvas 렌더는 meta.original로 fallback (render-service.ts).
      // panel textarea가 layer.text.value를 binding하므로 빈 값에서 시작해야
      // 사용자가 어디에 번역문을 써야 할지 헷갈리지 않는다. (issue #29)
      value: translated || '',
      font: AI_TEXT_FONT,
      size: AI_TEXT_SIZE,
      unit: 'px',
      lineHeight: 0,
      spacing: 0,
      color: AI_TEXT_COLOR,
      align: 'center',
      verticalAlign: 'middle',
    },
    meta,
  })
}

function polygonFromPayload(value: unknown): TextPolygon | undefined {
  if (!Array.isArray(value) || value.length === 0) return undefined
  const points: TextPolygon = []
  for (const raw of value) {
    if (!Array.isArray(raw) || raw.length < 2) continue
    const x = Number(raw[0])
    const y = Number(raw[1])
    if (Number.isFinite(x) && Number.isFinite(y)) points.push([x, y])
  }
  return points.length > 0 ? points : undefined
}

function writingModeFromPayload(value: unknown): WritingMode | undefined {
  return value === 'horizontal' || value === 'vertical' ? value : undefined
}

function numberOrUndefined(value: unknown): number | undefined {
  if (value == null) return undefined
  const n = Number(value)
  return Number.isFinite(n) ? n : undefined
}

function stringOrUndefined(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined
}

function bboxFromPayload(value: unknown): { x: number; y: number; width: number; height: number } {
  // 모델엔진 실응답: [x, y, w, h] 배열 형식
  if (Array.isArray(value) && value.length >= 4) {
    return {
      x: positiveOrZero(value[0], 0),
      y: positiveOrZero(value[1], 0),
      width: positiveNumber(value[2], 1),
      height: positiveNumber(value[3], 1),
    }
  }
  const payload = isRecord(value) ? value : {}
  return {
    x: positiveOrZero(payload.x ?? payload.left, 0),
    y: positiveOrZero(payload.y ?? payload.top, 0),
    width: positiveNumber(payload.width ?? payload.w, 1),
    height: positiveNumber(payload.height ?? payload.h, 1),
  }
}

function collectBitmapArtifactPatches(snapshot: AiJobSnapshot): BitmapArtifactPatch[] {
  const patches: BitmapArtifactPatch[] = []
  const seen = new Set<string>()

  for (const patch of snapshot.documentPatch.patches) {
    if (patch.op === 'add_layer') {
      const layerPayload = isRecord(patch.payload.layer) ? patch.payload.layer : undefined
      const artifactRef = stringValue(layerPayload?.source_ref ?? layerPayload?.sourceRef)
      if (artifactRef && isBitmapArtifact(snapshot, artifactRef) && !seen.has(artifactRef)) {
        seen.add(artifactRef)
        patches.push({ artifactRef, layerPayload })
      }
      continue
    }

    if (patch.op === 'replace_source_ref') {
      const artifactRef = stringValue(patch.payload.source_ref ?? patch.payload.sourceRef)
      if (artifactRef && isBitmapArtifact(snapshot, artifactRef) && !seen.has(artifactRef)) {
        seen.add(artifactRef)
        patches.push({ artifactRef })
      }
    }
  }

  return patches
}

function isBitmapArtifact(snapshot: AiJobSnapshot, artifactRef: string): boolean {
  const descriptor = snapshot.artifacts[artifactRef]
  if (!descriptor) {
    return false
  }
  return descriptor.kind === 'bitmap' || descriptor.media_type.startsWith('image/')
}

function createAiGraphicLayer(
  canvas: HTMLCanvasElement,
  layerPayload: Record<string, unknown> | undefined,
  operationLabel: string,
  timestamp: string,
  index: number,
): Layer {
  // model-engine이 patch.payload.layer.width/height를 명시했다면 그것이 곧
  // document 좌표계 상의 layer 영역. 없을 때만 bitmap의 native 크기로 fallback.
  // 기존 코드는 항상 canvas.width/height로 덮어써서 model-engine 지정 영역이
  // 무시되고 좌표계 mismatch가 났음 (issue #12).
  const payloadWidth = positiveOrUndefined(layerPayload?.width)
  const payloadHeight = positiveOrUndefined(layerPayload?.height)
  return LayerFactory.create({
    name: aiLayerName(operationLabel, timestamp, index),
    type: LayerTypes.LAYER_GRAPHIC,
    source: canvas,
    left: positiveOrZero(layerPayload?.left, 0),
    top: positiveOrZero(layerPayload?.top, 0),
    width: payloadWidth ?? canvas.width,
    height: payloadHeight ?? canvas.height,
    transparent: true,
    visible: true,
    // bitmap artifact는 현재 inpaint/pipeline operation에서만 생성됨.
    // LayerPanel은 meta.role로 카테고리 분류 — 이게 없으면 'custom'으로 떨어져
    // 텍스트 레이어 위에 쌓이면서 번역 텍스트가 가려진다 (issue #50).
    meta: { role: 'inpaint' },
  })
}

function positiveOrUndefined(value: unknown): number | undefined {
  return typeof value === 'number' && value > 0 ? value : undefined
}

function aiLayerName(operationLabel: string, timestamp: string, index: number): string {
  return `AI ${operationLabel} ${timestamp} #${String(index).padStart(2, '0')}`
}

function formatLayerTimestamp(date: Date): string {
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const min = String(date.getMinutes()).padStart(2, '0')
  return `${yyyy}${mm}${dd} ${hh}${min}`
}

function toOperationLabel(operationKind: AiJobSnapshot['operationKind']): string {
  return {
    detect: 'Detect',
    inpaint: 'Inpaint',
    translate: 'Translate',
    pipeline: 'Pipeline',
  }[operationKind]
}

function positiveNumber(value: unknown, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function positiveOrZero(value: unknown, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value : value == null ? '' : String(value)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}
