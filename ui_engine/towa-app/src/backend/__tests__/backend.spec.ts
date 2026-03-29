import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BackendError } from '@/backend/errors'
import { createAppBackend } from '@/backend/index'
import { createEmulatedAppBackend } from '@/backend/emulated'
import { createRealAppBackend } from '@/backend/real'

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

  it('forwards auth headers and snake_case payloads to model engine', async () => {
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
    expect(JSON.parse(String(requestInit?.body))).toMatchObject({
      schema_version: 'v1',
      idempotency_key: 'project:proj-1:page:001:op:detect:v:1',
      operation_kind: 'detect',
      request_ref: 'project/proj-1/page/001',
    })
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
