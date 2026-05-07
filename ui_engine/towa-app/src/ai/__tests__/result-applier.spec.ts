import { describe, expect, it, vi } from 'vitest'
import type { Store } from 'vuex'

import type { AiJobSnapshot } from '@/backend/contracts'
import type { Page } from '@/types/page'
import { applyAiJobSnapshotToCurrentPage } from '@/ai/result-applier'
import { blobToCanvas } from '@bitmappery/utils/canvas-util'

vi.mock('@bitmappery/utils/canvas-util', () => ({
  blobToCanvas: vi.fn(),
}))

describe('applyAiJobSnapshotToCurrentPage', () => {
  it('replaces page textBlocks and creates new text layers for succeeded jobs', async () => {
    const page = makePage()
    const store = makeStore(page)
    const savePage = vi.fn().mockResolvedValue(undefined)
    const snapshot = makeSnapshot({
      operationKind: 'translate',
      documentPatch: {
        patches: [
          {
            op: 'replace_text_blocks',
            payload: {
              text_blocks: [
                {
                  block_id: 'tb-new',
                  source_lang_text: 'hello',
                  translated_text: '안녕',
                  bbox: { x: 10, y: 20, width: 100, height: 50 },
                },
              ],
            },
          },
        ],
      },
    })

    const result = await applyAiJobSnapshotToCurrentPage({
      store,
      backend: { getArtifact: vi.fn() },
      snapshot,
      projectId: page.projectId,
      pageId: page.id,
      savePage,
      appliedAt: new Date(2026, 4, 7, 15, 30),
    })

    expect(result).toMatchObject({ applied: true, textLayerCount: 1, graphicLayerCount: 0 })
    expect(store.commit).toHaveBeenCalledWith(
      'pages/UPDATE_PAGE',
      expect.objectContaining({
        status: 'in-progress',
        textBlocks: [
          expect.objectContaining({
            id: 'tb-new',
            translated: '안녕',
            font: 'Noto Sans KR',
            fontSize: 24,
            color: '#000000',
          }),
        ],
      }),
    )
    expect(store.commit).toHaveBeenCalledWith(
      'bmp/addLayer',
      expect.objectContaining({
        name: 'AI Translate 20260507 1530 #01',
        type: 'text',
        left: 10,
        top: 20,
        width: 100,
        height: 50,
        text: expect.objectContaining({
          value: '안녕',
          font: 'Noto Sans KR',
          size: 24,
          color: '#000000',
        }),
      }),
    )
    expect(savePage).toHaveBeenCalledWith(page.id)
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
      backend: { getArtifact },
      snapshot,
      projectId: page.projectId,
      pageId: page.id,
      savePage: vi.fn().mockResolvedValue(undefined),
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
      }),
    )
    expect(store.commit).not.toHaveBeenCalledWith('bmp/updateLayer', expect.anything())
  })

  it('does not apply partial jobs automatically', async () => {
    const store = makeStore(makePage())
    const savePage = vi.fn()
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
      backend: { getArtifact: vi.fn() },
      snapshot,
      projectId: 'proj-1',
      pageId: 'page-1',
      savePage,
    })

    expect(result).toMatchObject({ applied: false, reason: 'status_not_succeeded' })
    expect(store.commit).not.toHaveBeenCalled()
    expect(savePage).not.toHaveBeenCalled()
  })
})

function makeStore(page: Page): Store<unknown> {
  return {
    getters: {
      'pages/byId': (projectId: string, pageId: string) => (
        projectId === page.projectId && pageId === page.id ? page : undefined
      ),
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
    textBlocks: [
      {
        id: 'tb-old',
        pageId: 'page-1',
        bbox: { x: 1, y: 2, width: 3, height: 4 },
        original: 'old',
        translated: '',
        font: 'Noto Sans KR',
        fontSize: 24,
        color: '#000000',
        status: 'detected',
      },
    ],
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
