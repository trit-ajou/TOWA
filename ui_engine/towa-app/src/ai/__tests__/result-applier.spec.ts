import { describe, expect, it, vi } from 'vitest'
import type { Store } from 'vuex'
import { QueryClient } from '@tanstack/vue-query'

import type { AiJobSnapshot } from '@/backend/contracts'
import type { FileAdapter } from '@/file-adapter'
import type { Page } from '@/types/page'
import type { PageSummary } from '@/file-adapter'
import { applyAiJobSnapshotToCurrentPage } from '@/ai/result-applier'
import { queryKeys } from '@/composables/queryKeys'
import { blobToCanvas } from '@bitmappery/utils/canvas-util'

function makeQueryClient(page: Page): QueryClient {
  const qc = new QueryClient()
  const summary: PageSummary = {
    id: page.id,
    projectId: page.projectId,
    index: page.index,
    status: page.status,
    updatedAt: new Date().toISOString(),
  }
  qc.setQueryData<PageSummary[]>(queryKeys.pages.byProject(page.projectId), [summary])
  return qc
}

// Minimal stub — background path is exercised by e2e, unit tests only cover
// the active path which never touches fileAdapter.
const stubFileAdapter = {} as FileAdapter

function makeAutoSaveStubs() {
  return {
    markDirty: vi.fn(),
    saveImmediately: vi.fn().mockResolvedValue(undefined),
  }
}

vi.mock('@bitmappery/utils/canvas-util', () => ({
  blobToCanvas: vi.fn(),
  canvasToBlob: vi.fn().mockResolvedValue(new Blob()),
}))

vi.mock('@bitmappery/utils/document-util', () => ({
  createSyncSnapshot: vi.fn(() => document.createElement('canvas')),
}))

vi.mock('@bitmappery/factories/document-factory', () => ({
  default: {
    fromBlob: vi.fn(),
    toBlob: vi.fn().mockResolvedValue(new Blob()),
  },
}))

describe('applyAiJobSnapshotToCurrentPage', () => {
  it('updates existing text layer in place on translate response (no remove/add)', async () => {
    const page = makePage()
    // detect가 만들어둔 layer. meta.blockId가 응답의 block_id와 매치되어야
    // translate 결과가 이 layer 위에 in-place로 반영된다. bbox는 layer 위치로
    // 표현되며 translate 응답이 와도 left/top/width/height는 건드리지 않는다.
    const existingTextLayer = {
      id: 'layer_99',
      type: 'text',
      left: 10,
      top: 20,
      width: 100,
      height: 50,
      text: { value: '', font: 'Noto Sans KR', size: 24, color: '#000000' },
      meta: {
        blockId: 'tb-existing',
        original: 'こんにちは',
        status: 'detected',
        boxMode: 'fixed',
        polygon: [[10, 20], [110, 20], [110, 70], [10, 70]],
        readingOrder: 1,
        writingMode: 'vertical',
        sourceRegionRef: 'region_0001',
      },
    }
    const store = makeStore(page, { layers: [existingTextLayer] })
    const autosave = makeAutoSaveStubs()
    const snapshot = makeSnapshot({
      operationKind: 'translate',
      documentPatch: {
        patches: [
          {
            op: 'replace_text_blocks',
            payload: {
              text_blocks: [
                {
                  block_id: 'tb-existing',
                  source_lang_text: 'こんにちは',
                  translated_text: '안녕하세요',
                  bbox: { x: 10, y: 20, width: 100, height: 50 },
                  reading_order: 1,
                  writing_mode: 'vertical',
                },
              ],
            },
          },
        ],
      },
    })

    const qc = makeQueryClient(page)
    const result = await applyAiJobSnapshotToCurrentPage({
      store,
      queryClient: qc,
      backend: { getArtifact: vi.fn() },
      snapshot,
      projectId: page.projectId,
      pageId: page.id,
      fileAdapter: stubFileAdapter,
      markDirty: autosave.markDirty,
      saveImmediately: autosave.saveImmediately,
      appliedAt: new Date(2026, 4, 7, 15, 30),
    })

    expect(result).toMatchObject({ applied: true, textLayerCount: 1, graphicLayerCount: 0 })
    // 기존 layer를 in-place 갱신. text.value만 번역문으로 바뀌고 status는 translated.
    expect(store.commit).toHaveBeenCalledWith('bmp/updateLayer', {
      index: 0,
      opts: {
        text: expect.objectContaining({ value: '안녕하세요' }),
        meta: expect.objectContaining({
          blockId: 'tb-existing',
          original: 'こんにちは',
          status: 'translated',
          polygon: [[10, 20], [110, 20], [110, 70], [10, 70]],
          readingOrder: 1,
          writingMode: 'vertical',
          sourceRegionRef: 'region_0001',
        }),
      },
    })
    // layer 삭제/신규 생성은 절대 일어나지 않아야 한다.
    expect(store.commit).not.toHaveBeenCalledWith('bmp/removeLayer', expect.anything())
    expect(store.commit).not.toHaveBeenCalledWith('bmp/addLayer', expect.anything())

    const cached = qc.getQueryData<PageSummary[]>(queryKeys.pages.byProject(page.projectId)) ?? []
    expect(cached.find((p) => p.id === page.id)?.status).toBe('in-progress')
    expect(autosave.saveImmediately).toHaveBeenCalledWith(page.id)
  })

  it('skips translate response blocks that do not match any existing layer', async () => {
    const page = makePage()
    const existingTextLayer = {
      id: 'layer_99',
      type: 'text',
      left: 0, top: 0, width: 100, height: 50,
      text: { value: '', font: 'Noto Sans KR', size: 24, color: '#000000' },
      meta: { blockId: 'tb-existing', original: 'a', status: 'detected', boxMode: 'fixed' },
    }
    const store = makeStore(page, { layers: [existingTextLayer] })
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const snapshot = makeSnapshot({
      operationKind: 'translate',
      documentPatch: {
        patches: [
          {
            op: 'replace_text_blocks',
            payload: {
              text_blocks: [
                { block_id: 'tb-orphan', source_lang_text: 'x', translated_text: 'y' },
              ],
            },
          },
        ],
      },
    })

    const result = await applyAiJobSnapshotToCurrentPage({
      store,
      queryClient: makeQueryClient(page),
      backend: { getArtifact: vi.fn() },
      snapshot,
      projectId: page.projectId,
      pageId: page.id,
      fileAdapter: stubFileAdapter,
      markDirty: vi.fn(),
      saveImmediately: vi.fn().mockResolvedValue(undefined),
    })

    expect(result.textLayerCount).toBe(0)
    expect(store.commit).not.toHaveBeenCalledWith('bmp/updateLayer', expect.anything())
    expect(store.commit).not.toHaveBeenCalledWith('bmp/addLayer', expect.anything())
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })

  it('preserves polygon/reading_order/writing_mode/source_region_ref from detect response onto meta', async () => {
    const page = makePage()
    const store = makeStore(page)
    const snapshot = makeSnapshot({
      operationKind: 'detect',
      documentPatch: {
        patches: [
          {
            op: 'replace_text_blocks',
            payload: {
              text_blocks: [
                {
                  block_id: 'tb-1',
                  source_lang_text: 'こんにちは',
                  bbox: { x: 10, y: 20, width: 100, height: 50 },
                  polygon: [[10, 20], [110, 20], [110, 70], [10, 70]],
                  reading_order: 3,
                  writing_mode: 'vertical',
                  source_region_ref: 'region_0001',
                },
              ],
            },
          },
        ],
      },
    })

    await applyAiJobSnapshotToCurrentPage({
      store,
      queryClient: makeQueryClient(page),
      backend: { getArtifact: vi.fn() },
      snapshot,
      projectId: page.projectId,
      pageId: page.id,
      fileAdapter: stubFileAdapter,
      markDirty: vi.fn(),
      saveImmediately: vi.fn().mockResolvedValue(undefined),
      appliedAt: new Date(2026, 4, 7, 15, 30),
    })

    expect(store.commit).toHaveBeenCalledWith(
      'bmp/addLayer',
      expect.objectContaining({
        meta: expect.objectContaining({
          blockId: 'tb-1',
          original: 'こんにちは',
          polygon: [[10, 20], [110, 20], [110, 70], [10, 70]],
          readingOrder: 3,
          writingMode: 'vertical',
          sourceRegionRef: 'region_0001',
        }),
      }),
    )
  })

  it('adds bitmap artifact results as new graphic layers without replacing existing layers', async () => {
    const page = makePage()
    const store = makeStore(page)
    const getArtifact = vi.fn().mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
    vi.mocked(blobToCanvas).mockResolvedValue({ width: 800, height: 1200 } as HTMLCanvasElement)
    const snapshot = makeSnapshot({
      operationKind: 'inpaint',
      artifacts: {
        'artifact://output/inpaint.png': {
          artifact_ref: 'artifact://output/inpaint.png',
          kind: 'bitmap',
          media_type: 'image/png',
          uri: 'file:///tmp/inpaint.png',
        },
      },
      documentPatch: {
        patches: [
          {
            op: 'add_layer',
            payload: {
              layer: {
                id: 'model-layer-1',
                type: 'graphic',
                left: 4,
                top: 8,
                width: 800,
                height: 1200,
                source_ref: 'artifact://output/inpaint.png',
              },
            },
          },
        ],
      },
    })

    const result = await applyAiJobSnapshotToCurrentPage({
      store,
      queryClient: makeQueryClient(page),
      backend: { getArtifact },
      snapshot,
      projectId: page.projectId,
      pageId: page.id,
      fileAdapter: stubFileAdapter,
      markDirty: vi.fn(),
      saveImmediately: vi.fn().mockResolvedValue(undefined),
      appliedAt: new Date(2026, 4, 7, 15, 30),
    })

    expect(result).toMatchObject({ applied: true, textLayerCount: 0, graphicLayerCount: 1 })
    expect(getArtifact).toHaveBeenCalledWith('job-1', 'artifact://output/inpaint.png', undefined)
    expect(store.commit).toHaveBeenCalledWith(
      'bmp/addLayer',
      expect.objectContaining({
        name: 'AI Inpaint 20260507 1530 #01',
        type: 'graphic',
        left: 4,
        top: 8,
        width: 800,
        height: 1200,
        meta: expect.objectContaining({ role: 'inpaint' }),
      }),
    )
    expect(store.commit).not.toHaveBeenCalledWith('bmp/removeLayer', expect.anything())
  })

  it('inserts inpaint graphic layer below existing text layers so text stays on top', async () => {
    const page = makePage()
    const existingText = { id: 'layer_99', type: 'text' }
    const store = makeStore(page, { width: 800, height: 1200, layers: [existingText] })
    const getArtifact = vi.fn().mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
    vi.mocked(blobToCanvas).mockResolvedValue({ width: 800, height: 1200 } as HTMLCanvasElement)
    const snapshot = makeSnapshot({
      operationKind: 'inpaint',
      artifacts: {
        'artifact://output/inpaint.png': {
          artifact_ref: 'artifact://output/inpaint.png',
          kind: 'bitmap',
          media_type: 'image/png',
          uri: 'file:///tmp/inpaint.png',
        },
      },
      documentPatch: {
        patches: [
          {
            op: 'add_layer',
            payload: {
              layer: {
                id: 'g-1',
                type: 'graphic',
                left: 0,
                top: 0,
                width: 800,
                height: 1200,
                source_ref: 'artifact://output/inpaint.png',
              },
            },
          },
        ],
      },
    })

    await applyAiJobSnapshotToCurrentPage({
      store,
      queryClient: makeQueryClient(page),
      backend: { getArtifact },
      snapshot,
      projectId: page.projectId,
      pageId: page.id,
      fileAdapter: stubFileAdapter,
      markDirty: vi.fn(),
      saveImmediately: vi.fn().mockResolvedValue(undefined),
      appliedAt: new Date(2026, 4, 7, 15, 30),
    })

    // 기존 텍스트 인덱스 0 직전에 insert → graphic이 텍스트 아래로 깔림
    expect(store.commit).toHaveBeenCalledWith(
      'bmp/insertLayerAtIndex',
      expect.objectContaining({
        index: 0,
        layer: expect.objectContaining({
          type: 'graphic',
          meta: expect.objectContaining({ role: 'inpaint' }),
        }),
      }),
    )
  })

  it('accepts bbox in [x, y, w, h] array form from model engine', async () => {
    const page = makePage()
    const store = makeStore(page)
    const snapshot = makeSnapshot({
      operationKind: 'detect',
      documentPatch: {
        patches: [
          {
            op: 'replace_text_blocks',
            payload: {
              text_blocks: [
                {
                  block_id: 'tb-arr',
                  source_lang_text: 'やあ',
                  bbox: [12, 34, 56, 78],
                },
              ],
            },
          },
        ],
      },
    })

    await applyAiJobSnapshotToCurrentPage({
      store,
      queryClient: makeQueryClient(page),
      backend: { getArtifact: vi.fn() },
      snapshot,
      projectId: page.projectId,
      pageId: page.id,
      fileAdapter: stubFileAdapter,
      markDirty: vi.fn(),
      saveImmediately: vi.fn().mockResolvedValue(undefined),
      appliedAt: new Date(2026, 4, 7, 15, 30),
    })

    expect(store.commit).toHaveBeenCalledWith(
      'bmp/addLayer',
      expect.objectContaining({
        left: 12,
        top: 34,
        // detect-only: translated_text 없으면 text.value는 빈 값. 원문은 meta.original에만.
        text: expect.objectContaining({ value: '' }),
        meta: expect.objectContaining({ original: 'やあ', status: 'detected' }),
      }),
    )
  })

  it('does not apply partial jobs automatically', async () => {
    const page = makePage()
    const store = makeStore(page)
    const autosave = makeAutoSaveStubs()
    const snapshot = makeSnapshot({
      status: 'partial',
      documentPatch: {
        patches: [
          {
            op: 'replace_text_blocks',
            payload: { text_blocks: [{ block_id: 'tb-new', bbox: { x: 1, y: 1, width: 10, height: 10 } }] },
          },
        ],
      },
    })

    const result = await applyAiJobSnapshotToCurrentPage({
      store,
      queryClient: makeQueryClient(page),
      backend: { getArtifact: vi.fn() },
      snapshot,
      projectId: 'proj-1',
      pageId: 'page-1',
      fileAdapter: stubFileAdapter,
      markDirty: autosave.markDirty,
      saveImmediately: autosave.saveImmediately,
    })

    expect(result).toMatchObject({ applied: false, reason: 'status_not_succeeded' })
    expect(store.commit).not.toHaveBeenCalled()
    expect(autosave.saveImmediately).not.toHaveBeenCalled()
  })
})

function makeStore(page: Page, activeDocument: { layers?: unknown[]; width?: number; height?: number } = {}): Store<unknown> {
  return {
    // Active-path branch checks state.editor.selectedPageId to decide whether
    // to mutate the live store or go via the detached background path.
    state: { editor: { selectedPageId: page.id } },
    getters: {
      'pages/byId': (projectId: string, pageId: string) => (
        projectId === page.projectId && pageId === page.id ? page : undefined
      ),
      'bmp/activeDocument': activeDocument,
    },
    commit: vi.fn(),
  } as unknown as Store<unknown>
}

function makePage(): Page {
  return {
    id: 'page-1',
    projectId: 'proj-1',
    index: 1,
    status: 'waiting',
  }
}

function makeSnapshot(overrides: Partial<AiJobSnapshot> = {}): AiJobSnapshot {
  return {
    jobId: 'job-1',
    pipelineId: 'pipe-1',
    status: 'succeeded',
    operationKind: 'translate',
    requestRef: 'project/proj-1/page/page-1',
    document: { id: 'doc-1' },
    documentPatch: { patches: [] },
    artifacts: {},
    stageReports: [],
    error: null,
    ...overrides,
  }
}
