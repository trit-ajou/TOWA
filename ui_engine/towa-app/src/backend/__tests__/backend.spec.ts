import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BackendError } from '@/backend/errors'
import { createAppBackend } from '@/backend/index'
import { createEmulatedAppBackend, createEmulatedFilesBackend } from '@/backend/emulated'
import { createRealAppBackend, createRealFilesBackend, parseMultipartMixed } from '@/backend/real'
import type { PageSnapshotPayload } from '@/backend/contracts'
import { createUlid, isCanonicalUlid } from '@/utils/ulid'

const TEST_PROJECT_ID = '01ARZ3NDEKTSV4RRFFQ69G5FAV'
const TEST_PAGE_ID_1 = '01ARZ3NDEKTSV4RRFFQ69G5FAW'
const TEST_PAGE_ID_2 = '01ARZ3NDEKTSV4RRFFQ69G5FAX'

describe('real backend adapters', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('maps dev login responses from service engine', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          session_key: 'session-1',
          expires_in: 86400,
          user: {
            id: 'user-1',
            email: 'user@example.com',
            nickname: 'tester',
            status: 'active',
            created_at: '2026-03-25T00:00:00Z',
          },
          credit_balance: 1000,
          reserved_units: 0,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    const backend = createRealAppBackend({
      serviceEngineUrl: 'http://localhost:8000',
      modelEngineUrl: 'http://localhost:8100',
    })
    const result = await backend.auth.devLogin({ email: 'user@example.com' })

    expect(result.sessionKey).toBe('session-1')
    expect(result.user.email).toBe('user@example.com')
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/auth/dev/login',
      expect.objectContaining({
        method: 'POST',
      }),
    )
  })

  it('posts model jobs as multipart metadata plus primary bitmap', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          job_id: 'job-1',
          pipeline_id: 'pipe-1',
          status: 'queued',
          operation_kind: 'detect',
          request_ref: 'project/proj-1/page/001',
          status_url: '/v1/jobs/job-1',
        }),
        { status: 202, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    const backend = createRealAppBackend({
      serviceEngineUrl: 'http://localhost:8000',
      modelEngineUrl: 'http://localhost:8100',
    })

    const result = await backend.aiJobs.createJob(
      {
        schemaVersion: 'v1',
        idempotencyKey: 'project:proj-1:page:001:op:detect:v:1',
        operationKind: 'detect',
        requestRef: 'project/proj-1/page/001',
        document: { id: 'doc-1' },
        artifacts: {},
        primaryBitmap: new Blob(['png'], { type: 'image/png' }),
        runtimeContext: { mode: 'saas', workspace_uri: 'workspace://project/proj-1/page/001' },
      },
      { sessionKey: 'demo-session' },
    )

    expect(result.jobId).toBe('job-1')
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8100/v1/jobs',
      expect.objectContaining({
        method: 'POST',
      }),
    )
    const requestInit = vi.mocked(fetch).mock.calls[0]?.[1]
    expect(requestInit).toBeTruthy()
    const headers = new Headers(requestInit?.headers)
    expect(headers.get('Authorization')).toBe('Bearer demo-session')
    expect(headers.get('Content-Type')).toBeNull()
    const body = requestInit?.body as FormData
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('primary_bitmap')).toBeInstanceOf(Blob)
    const metadata = JSON.parse(await (body.get('metadata') as Blob).text())
    expect(metadata).toMatchObject({
      schema_version: 'v1',
      idempotency_key: 'project:proj-1:page:001:op:detect:v:1',
      operation_kind: 'detect',
      request_ref: 'project/proj-1/page/001',
    })
    expect(metadata.artifacts['artifact://input/primary_bitmap']).toMatchObject({
      artifact_ref: 'artifact://input/primary_bitmap',
      kind: 'bitmap',
      media_type: 'image/png',
      uri: 'upload://primary_bitmap',
    })
  })

  it('maps document_patch from model job snapshots', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          job_id: 'job-1',
          pipeline_id: 'pipe-1',
          status: 'succeeded',
          operation_kind: 'translate',
          request_ref: 'project/proj-1/page/001',
          document: { id: 'doc-1' },
          document_patch: {
            patches: [
              {
                op: 'replace_text_blocks',
                payload: { text_blocks: [{ block_id: 'tb-1' }] },
              },
            ],
          },
          artifacts: {},
          stage_reports: [],
          error: null,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    const backend = createRealAppBackend({
      serviceEngineUrl: 'http://localhost:8000',
      modelEngineUrl: 'http://localhost:8100',
    })

    const snapshot = await backend.aiJobs.getJob('job-1', { sessionKey: 'demo-session' })

    expect(snapshot.documentPatch.patches).toHaveLength(1)
    expect(snapshot.documentPatch.patches[0].op).toBe('replace_text_blocks')
  })

  it('downloads model job artifacts as blobs with auth headers', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(new Blob(['artifact'], { type: 'image/png' }), {
        status: 200,
        headers: { 'Content-Type': 'image/png' },
      }),
    )

    const backend = createRealAppBackend({
      serviceEngineUrl: 'http://localhost:8000',
      modelEngineUrl: 'http://localhost:8100',
    })

    const blob = await backend.aiJobs.getArtifact(
      'job-1',
      'artifact://output/inpaint.png',
      { sessionKey: 'demo-session' },
    )

    expect(blob.type).toBe('image/png')
    expect(await blob.text()).toBe('artifact')
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8100/v1/jobs/job-1/artifacts?artifact_ref=artifact%3A%2F%2Foutput%2Finpaint.png',
      expect.objectContaining({
        method: 'GET',
      }),
    )
    const requestInit = vi.mocked(fetch).mock.calls[0]?.[1]
    const headers = new Headers(requestInit?.headers)
    expect(headers.get('Authorization')).toBe('Bearer demo-session')
  })

  it('raises BackendError for engine error envelopes', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: 'session_invalid',
            message: 'invalid session',
            retryable: false,
            details: null,
          },
        }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    const backend = createRealAppBackend({
      serviceEngineUrl: 'http://localhost:8000',
      modelEngineUrl: 'http://localhost:8100',
    })

    await expect(backend.auth.getCurrentUser({ sessionKey: 'bad-session' })).rejects.toMatchObject({
      payload: {
        code: 'session_invalid',
      },
    })
  })

  it('wraps malformed JSON responses as BackendError', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response('not-json', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    const backend = createRealAppBackend({
      serviceEngineUrl: 'http://localhost:8000',
      modelEngineUrl: 'http://localhost:8100',
    })

    await expect(backend.auth.devLogin({ email: 'user@example.com' })).rejects.toMatchObject({
      payload: {
        code: 'invalid_response',
      },
    })
  })

  it('wraps network failures as BackendError', async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError('fetch failed'))

    const backend = createRealAppBackend({
      serviceEngineUrl: 'http://localhost:8000',
      modelEngineUrl: 'http://localhost:8100',
    })

    await expect(backend.auth.devLogin({ email: 'user@example.com' })).rejects.toMatchObject({
      payload: {
        code: 'backend_unreachable',
      },
    })
  })
})

describe('emulated backend adapters', () => {
  it('emulates login and polling lifecycle without network calls', async () => {
    const backend = createEmulatedAppBackend()
    const login = await backend.auth.devLogin({ email: 'user@example.com' })
    const currentUser = await backend.auth.getCurrentUser({ sessionKey: login.sessionKey })

    expect(currentUser.user.email).toBe('user@example.com')

    const created = await backend.aiJobs.createJob(
      {
        idempotencyKey: 'project:proj-1:page:001:op:translate:v:1',
        operationKind: 'translate',
        requestRef: 'project/proj-1/page/001',
        document: { id: 'doc-1', stage_meta: {} },
        artifacts: {},
        primaryBitmap: new Blob(['png'], { type: 'image/png' }),
        runtimeContext: { mode: 'saas', workspace_uri: 'workspace://project/proj-1/page/001' },
      },
      { sessionKey: login.sessionKey },
    )
    const running = await backend.aiJobs.getJob(created.jobId, { sessionKey: login.sessionKey })
    const terminal = await backend.aiJobs.getJob(created.jobId, { sessionKey: login.sessionKey })

    expect(created.status).toBe('queued')
    expect(running.status).toBe('running')
    expect(terminal.status).toBe('succeeded')
    expect(terminal.document.stage_meta).toMatchObject({
      translation: {
        executor: 'emulated',
      },
    })
    expect(terminal.documentPatch.patches[0].op).toBe('replace_text_blocks')
  })

  it('scopes emulated saas jobs to the creating session and rejects mismatch payloads', async () => {
    const backend = createEmulatedAppBackend()
    const firstLogin = await backend.auth.devLogin({ email: 'first@example.com' })
    const secondLogin = await backend.auth.devLogin({ email: 'second@example.com' })

    const created = await backend.aiJobs.createJob(
      {
        idempotencyKey: 'project:proj-1:page:001:op:detect:v:1',
        operationKind: 'detect',
        requestRef: 'project/proj-1/page/001',
        document: { id: 'doc-1', stage_meta: {} },
        artifacts: {},
        primaryBitmap: new Blob(['png'], { type: 'image/png' }),
        runtimeContext: { mode: 'saas', workspace_uri: 'workspace://project/proj-1/page/001' },
      },
      { sessionKey: firstLogin.sessionKey },
    )

    await expect(
      backend.aiJobs.getJob(created.jobId, { sessionKey: secondLogin.sessionKey }),
    ).rejects.toMatchObject({
      payload: {
        code: 'model_job_not_found',
      },
    })

    await expect(
      backend.aiJobs.createJob(
        {
          idempotencyKey: 'project:proj-1:page:001:op:detect:v:1',
          operationKind: 'translate',
          requestRef: 'project/proj-1/page/001',
          document: { id: 'doc-1', stage_meta: {} },
          artifacts: {},
          primaryBitmap: new Blob(['png'], { type: 'image/png' }),
          runtimeContext: { mode: 'saas', workspace_uri: 'workspace://project/proj-1/page/001' },
        },
        { sessionKey: firstLogin.sessionKey },
      ),
    ).rejects.toMatchObject({
      payload: {
        code: 'model_job_conflict',
      },
    })
  })
})

describe('backend factory', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('supports mixing emulated auth with real ai adapters', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          job_id: 'job-1',
          pipeline_id: 'pipe-1',
          status: 'queued',
          operation_kind: 'detect',
          request_ref: 'project/proj-1/page/001',
          status_url: '/v1/jobs/job-1',
        }),
        { status: 202, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    const backend = createAppBackend({
      authMode: 'emulated',
      aiMode: 'real',
      serviceEngineUrl: 'http://localhost:8000',
      modelEngineUrl: 'http://localhost:8100',
    })

    const login = await backend.auth.devLogin({ email: 'user@example.com' })
    const created = await backend.aiJobs.createJob(
      {
        idempotencyKey: 'project:proj-1:page:001:op:detect:v:2',
        operationKind: 'detect',
        requestRef: 'project/proj-1/page/001',
        document: { id: 'doc-1' },
        artifacts: {},
        primaryBitmap: new Blob(['png'], { type: 'image/png' }),
        runtimeContext: { mode: 'local', workspace_uri: 'workspace://project/proj-1/page/001' },
      },
      { sessionKey: login.sessionKey },
    )

    expect(created.jobId).toBe('job-1')
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})

describe('shared error helpers', () => {
  it('exposes typed backend errors', () => {
    const error = new BackendError({
      code: 'demo_error',
      message: 'demo',
      retryable: false,
      details: null,
    })

    expect(error.payload.code).toBe('demo_error')
    expect(error.message).toBe('demo')
  })
})

// --- FilesBackend tests ---

function makeSnapshot(overrides: {
  pageId?: string
  projectId?: string
  index?: number
  status?: string
}): PageSnapshotPayload {
  return {
    metadata: {
      page: {
        id: overrides.pageId ?? TEST_PAGE_ID_1,
        projectId: overrides.projectId ?? TEST_PROJECT_ID,
        index: overrides.index ?? 1,
        status: overrides.status ?? 'waiting',
        textBlocks: [
          {
            id: 'tb-1',
            pageId: overrides.pageId ?? TEST_PAGE_ID_1,
            bbox: { x: 10, y: 20, width: 100, height: 50 },
            original: 'hello',
            translated: '안녕',
            font: 'Noto Sans KR',
            fontSize: 14,
            color: '#000',
            status: 'translated',
          },
        ],
      },
    },
    originalImage: new Blob(['img'], { type: 'image/png' }),
    layerBlob: new Blob(['layer'], { type: 'application/octet-stream' }),
    thumbnail: new Blob(['thumb'], { type: 'image/jpeg' }),
  }
}

describe('emulated FilesBackend', () => {
  it('round-trip: createProject → createPage → list → save → get → delete → dense index', async () => {
    const files = createEmulatedFilesBackend()
    const opts = { sessionKey: 'test-key' }

    // Create project
    const project = await files.createProject(
      { id: TEST_PROJECT_ID, name: 'Test', sourceLang: 'ja', targetLang: 'ko' },
      opts,
    )
    expect(project.id).toBe(TEST_PROJECT_ID)
    expect(project.pageCount).toBe(0)

    // Create page 1
    const snap1 = makeSnapshot({ pageId: TEST_PAGE_ID_1, projectId: TEST_PROJECT_ID, index: 1 })
    const summary1 = await files.createPage(TEST_PROJECT_ID, snap1, opts)
    expect(summary1.index).toBe(1)

    // Create page 2
    const snap2 = makeSnapshot({ pageId: TEST_PAGE_ID_2, projectId: TEST_PROJECT_ID, index: 2 })
    const summary2 = await files.createPage(TEST_PROJECT_ID, snap2, opts)
    expect(summary2.index).toBe(2)

    // List pages
    const summaries = await files.listPageSummaries(TEST_PROJECT_ID, opts)
    expect(summaries).toHaveLength(2)

    // Save page snapshot (update status)
    const updatedSnap = makeSnapshot({ pageId: TEST_PAGE_ID_1, projectId: TEST_PROJECT_ID, index: 1, status: 'in-progress' })
    const saved = await files.savePageSnapshot(TEST_PAGE_ID_1, updatedSnap, opts)
    expect(saved.status).toBe('in-progress')

    // Get page snapshot
    const loaded = await files.getPageSnapshot(TEST_PAGE_ID_1, opts)
    expect(loaded.metadata.page.status).toBe('in-progress')
    expect(loaded.metadata.page.textBlocks).toHaveLength(1)

    // Delete page 1 → page 2 should become index 1
    await files.deletePage(TEST_PAGE_ID_1, opts)
    const remaining = await files.listPageSummaries(TEST_PROJECT_ID, opts)
    expect(remaining).toHaveLength(1)
    expect(remaining[0].id).toBe(TEST_PAGE_ID_2)
    expect(remaining[0].index).toBe(1)

    // Project pageCount should be updated
    const proj = await files.getProject(TEST_PROJECT_ID, opts)
    expect(proj.pageCount).toBe(1)
  })

  it('rejects createPage with wrong index (append-only violation)', async () => {
    const files = createEmulatedFilesBackend()
    const opts = { sessionKey: 'test-key' }

    await files.createProject(
      { id: TEST_PROJECT_ID, name: 'Test', sourceLang: 'ja', targetLang: 'ko' },
      opts,
    )

    // Try to create page with index 5 when it should be 1
    const snap = makeSnapshot({ pageId: TEST_PAGE_ID_1, projectId: TEST_PROJECT_ID, index: 5 })
    await expect(files.createPage(TEST_PROJECT_ID, snap, opts)).rejects.toMatchObject({
      payload: {
        code: 'page_conflict',
        details: { reason: 'index_invalid' },
      },
    })
  })

  it('rejects createPage with duplicate id', async () => {
    const files = createEmulatedFilesBackend()
    const opts = { sessionKey: 'test-key' }

    await files.createProject(
      { id: TEST_PROJECT_ID, name: 'Test', sourceLang: 'ja', targetLang: 'ko' },
      opts,
    )

    const snap1 = makeSnapshot({ pageId: TEST_PAGE_ID_1, projectId: TEST_PROJECT_ID, index: 1 })
    await files.createPage(TEST_PROJECT_ID, snap1, opts)

    // Same page id again
    const snap2 = makeSnapshot({ pageId: TEST_PAGE_ID_1, projectId: TEST_PROJECT_ID, index: 2 })
    await expect(files.createPage(TEST_PROJECT_ID, snap2, opts)).rejects.toMatchObject({
      payload: { code: 'page_conflict' },
    })
  })

  it('rejects all methods when sessionKey is missing', async () => {
    const files = createEmulatedFilesBackend()
    await expect(files.listProjects({})).rejects.toMatchObject({
      payload: { code: 'session_key_required' },
    })
  })
})

describe('real FilesBackend', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('normalizes layer_blob to application/octet-stream for savePageSnapshot', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          page: {
            id: TEST_PAGE_ID_1,
            project_id: TEST_PROJECT_ID,
            index: 1,
            status: 'in-progress',
            thumbnail_url: null,
            updated_at: '2026-04-15T00:00:00Z',
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    const backend = createRealFilesBackend({
      serviceEngineUrl: 'http://localhost:8000',
      modelEngineUrl: 'http://localhost:8100',
    })

    const snapshot = {
      ...makeSnapshot({ pageId: TEST_PAGE_ID_1, projectId: TEST_PROJECT_ID, index: 1 }),
      layerBlob: new Blob(['layer'], { type: 'text/plain;charset=utf-8' }),
    }
    const result = await backend.savePageSnapshot(TEST_PAGE_ID_1, snapshot, { sessionKey: 'demo-session' })

    expect(result.id).toBe(TEST_PAGE_ID_1)
    expect(fetch).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/pages/${TEST_PAGE_ID_1}/snapshot`,
      expect.objectContaining({ method: 'PUT' }),
    )

    // Check authorization header
    const callArgs = vi.mocked(fetch).mock.calls[0]
    const headers = callArgs[1]?.headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer demo-session')

    // Check FormData parts
    const body = callArgs[1]?.body as FormData
    expect(body.get('metadata')).toBeTruthy()
    expect(body.get('original_image')).toBeTruthy()
    expect(body.get('layer_blob')).toBeTruthy()
    expect(body.get('thumbnail')).toBeTruthy()
    expect(body.get('layer_blob')).toBeInstanceOf(Blob)
    expect((body.get('layer_blob') as Blob).type).toBe('application/octet-stream')
  })

  it('parses multipart/mixed response for getPageSnapshot', async () => {
    const boundary = 'test-boundary-123'
    const metadataJson = JSON.stringify({
      page: {
        id: TEST_PAGE_ID_1,
        project_id: TEST_PROJECT_ID,
        index: 1,
        status: 'waiting',
        text_blocks: [
          {
            id: 'tb-1',
            page_id: TEST_PAGE_ID_1,
            bbox: { x: 10, y: 20, width: 100, height: 50 },
            original: 'hello',
            translated: '안녕',
            font: 'Noto Sans KR',
            font_size: 14,
            color: '#000',
            status: 'translated',
          },
        ],
      },
    })

    const bodyParts = [
      `--${boundary}\r\n`,
      'Content-Disposition: form-data; name="metadata"\r\n',
      'Content-Type: application/json\r\n',
      '\r\n',
      metadataJson,
      `\r\n--${boundary}\r\n`,
      'Content-Disposition: form-data; name="original_image"\r\n',
      'Content-Type: image/png\r\n',
      '\r\n',
      'IMGDATA',
      `\r\n--${boundary}\r\n`,
      'Content-Disposition: form-data; name="layer_blob"\r\n',
      'Content-Type: application/octet-stream\r\n',
      '\r\n',
      'LAYERDATA',
      `\r\n--${boundary}\r\n`,
      'Content-Disposition: form-data; name="thumbnail"\r\n',
      'Content-Type: image/jpeg\r\n',
      '\r\n',
      'THUMBDATA',
      `\r\n--${boundary}--\r\n`,
    ].join('')

    const response = new Response(bodyParts, {
      status: 200,
      headers: { 'Content-Type': `multipart/mixed; boundary=${boundary}` },
    })

    const payload = await parseMultipartMixed(response)

    expect(payload.metadata.page.id).toBe(TEST_PAGE_ID_1)
    expect(payload.metadata.page.projectId).toBe(TEST_PROJECT_ID)
    expect(payload.metadata.page.textBlocks).toHaveLength(1)
    expect(payload.metadata.page.textBlocks[0].fontSize).toBe(14)
    expect(payload.metadata.page.textBlocks[0].pageId).toBe(TEST_PAGE_ID_1)

    const imgText = await payload.originalImage.text()
    expect(imgText).toBe('IMGDATA')
    expect(payload.originalImage.type).toBe('image/png')

    const layerText = await payload.layerBlob.text()
    expect(layerText).toBe('LAYERDATA')

    const thumbText = await payload.thumbnail.text()
    expect(thumbText).toBe('THUMBDATA')
  })

  it('throws BackendError for error envelope from files endpoints', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: 'project_not_found',
            message: 'not found',
            retryable: false,
            details: null,
          },
        }),
        { status: 404, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    const backend = createRealFilesBackend({
      serviceEngineUrl: 'http://localhost:8000',
      modelEngineUrl: 'http://localhost:8100',
    })

    await expect(
      backend.getProject('nonexistent', { sessionKey: 'demo-session' }),
    ).rejects.toMatchObject({
      payload: { code: 'project_not_found' },
    })
  })

  it('throws session_key_required when sessionKey is missing', async () => {
    const backend = createRealFilesBackend({
      serviceEngineUrl: 'http://localhost:8000',
      modelEngineUrl: 'http://localhost:8100',
    })

    await expect(
      backend.listProjects({}),
    ).rejects.toMatchObject({
      payload: { code: 'session_key_required' },
    })
  })

  it('creates canonical ULIDs for new project/page IDs', () => {
    const projectId = createUlid()
    const pageId = createUlid()

    expect(isCanonicalUlid(projectId)).toBe(true)
    expect(isCanonicalUlid(pageId)).toBe(true)
    expect(projectId).not.toBe(pageId)
  })
})
