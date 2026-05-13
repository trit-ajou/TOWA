import type { Store } from 'vuex'

import type { AiJobSnapshot, AiJobsBackend, TransportPatchOperation } from '@/backend/contracts'
import type { Page } from '@/types/page'
import type { LayerTextMeta } from '@/types/text-block'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'
import type { Layer } from '@bitmappery/definitions/document'
import { LayerTypes } from '@bitmappery/definitions/layer-types'
// @ts-expect-error bitmappery JS module
import { blobToCanvas } from '@bitmappery/utils/canvas-util'

const AI_TEXT_FONT = 'Noto Sans KR'
const AI_TEXT_SIZE = 24
const AI_TEXT_COLOR = '#000000'

export interface ApplyAiJobSnapshotOptions {
  store: Store<unknown>
  backend: Pick<AiJobsBackend, 'getArtifact'>
  snapshot: AiJobSnapshot
  projectId: string
  pageId: string
  savePage: (pageId: string) => Promise<void>
  sessionKey?: string | null
  appliedAt?: Date
}

export interface ApplyAiJobSnapshotResult {
  applied: boolean
  reason?: string
  textLayerCount: number
  graphicLayerCount: number
}

interface BitmapArtifactPatch {
  artifactRef: string
  layerPayload?: Record<string, unknown>
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

  const page = options.store.getters['pages/byId'](options.projectId, options.pageId) as Page | undefined
  if (!page) {
    throw new Error(`Cannot apply AI result: page not found (${options.pageId})`)
  }

  const operationLabel = toOperationLabel(options.snapshot.operationKind)
  const timestamp = formatLayerTimestamp(options.appliedAt ?? new Date())
  const patches = options.snapshot.documentPatch.patches
  const textLayers: Layer[] = []
  let replaceTextLayers = false
  const docForSize = options.store.getters['bmp/activeDocument'] as { width?: number; height?: number } | undefined
  const docW = docForSize?.width ?? 800
  const docH = docForSize?.height ?? 1200

  for (const patch of patches) {
    if (patch.op !== 'replace_text_blocks' && patch.op !== 'append_text_blocks') {
      continue
    }
    if (patch.op === 'replace_text_blocks') {
      replaceTextLayers = true
    }
    const rawBlocks = textBlocksFromPatch(patch)
    for (const rawBlock of rawBlocks) {
      textLayers.push(createAiTextLayerFromPayload(rawBlock, operationLabel, timestamp, textLayers.length + 1, docW, docH))
    }
  }

  const graphicLayers: Layer[] = []
  const bitmapArtifactPatches = collectBitmapArtifactPatches(options.snapshot)
  for (const patch of bitmapArtifactPatches) {
    const blob = await options.backend.getArtifact(
      options.snapshot.jobId,
      patch.artifactRef,
      options.sessionKey ? { sessionKey: options.sessionKey } : undefined,
    )
    const canvas = await blobToCanvas(blob)
    graphicLayers.push(createAiGraphicLayer(canvas, patch.layerPayload, operationLabel, timestamp, graphicLayers.length + 1))
  }

  if (replaceTextLayers) {
    const activeDocument = options.store.getters['bmp/activeDocument'] as { layers?: Layer[] } | undefined
    const currentLayers = activeDocument?.layers ?? []
    for (let i = currentLayers.length - 1; i >= 0; i--) {
      if (currentLayers[i].type === LayerTypes.LAYER_TEXT) {
        options.store.commit('bmp/removeLayer', i)
      }
    }
  }

  for (const layer of textLayers) {
    options.store.commit('bmp/addLayer', layer)
  }
  for (const layer of graphicLayers) {
    options.store.commit('bmp/addLayer', layer)
  }

  options.store.commit('pages/UPDATE_PAGE', {
    ...page,
    status: 'in-progress',
  } satisfies Page)

  await options.savePage(options.pageId)
  return {
    applied: true,
    textLayerCount: textLayers.length,
    graphicLayerCount: graphicLayers.length,
  }
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
  const meta: LayerTextMeta = {
    blockId,
    original,
    status: translated ? 'translated' : 'detected',
  }
  // layer.width/height는 텍스트 렌더링 canvas 크기. bbox는 left/top으로만 반영하고
  // canvas 영역은 document 전체로 잡아 글자가 잘리지 않게 함.
  return LayerFactory.create({
    name: aiLayerName(operationLabel, timestamp, index),
    type: LayerTypes.LAYER_TEXT,
    left: bbox.x,
    top: bbox.y,
    width: docW,
    height: docH,
    transparent: true,
    visible: true,
    text: {
      value: translated || original,
      font: AI_TEXT_FONT,
      size: AI_TEXT_SIZE,
      unit: 'px',
      lineHeight: 0,
      spacing: 0,
      color: AI_TEXT_COLOR,
    },
    meta,
  })
}

function bboxFromPayload(value: unknown): { x: number; y: number; width: number; height: number } {
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
  return LayerFactory.create({
    name: aiLayerName(operationLabel, timestamp, index),
    type: LayerTypes.LAYER_GRAPHIC,
    source: canvas,
    left: positiveOrZero(layerPayload?.left, 0),
    top: positiveOrZero(layerPayload?.top, 0),
    width: canvas.width,
    height: canvas.height,
    transparent: true,
    visible: true,
  })
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
