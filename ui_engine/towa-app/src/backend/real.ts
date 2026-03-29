import type {
  AiJobCreateInput,
  AiJobCreateResult,
  AiJobSnapshot,
  AiJobsBackend,
  AppBackend,
  AuthBackend,
  AuthRequestOptions,
  CurrentSessionInfo,
  EngineError,
  LoginInput,
  LoginResult,
} from './contracts'
import { BackendError, ensureSessionKey } from './errors'

interface JsonObject {
  [key: string]: unknown
}

interface RealBackendOptions {
  serviceEngineUrl: string
  modelEngineUrl: string
}

export function createRealAppBackend(options: RealBackendOptions): AppBackend {
  return {
    auth: createRealAuthBackend(options),
    aiJobs: createRealAiJobsBackend(options),
  }
}

export function createRealAuthBackend(options: RealBackendOptions): AuthBackend {
  return {
    async devLogin(input: LoginInput): Promise<LoginResult> {
      const payload = await requestJson(`${options.serviceEngineUrl}/auth/dev/login`, {
        method: 'POST',
        body: JSON.stringify({
          email: input.email,
          nickname: input.nickname,
        }),
      })
      return toLoginResult(payload)
    },

    async getCurrentUser(requestOptions: AuthRequestOptions): Promise<CurrentSessionInfo> {
      const payload = await requestJson(`${options.serviceEngineUrl}/auth/me`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${ensureSessionKey(requestOptions.sessionKey)}`,
        },
      })
      return toCurrentSessionInfo(payload)
    },
  }
}

export function createRealAiJobsBackend(options: RealBackendOptions): AiJobsBackend {
  return {
    async createJob(input: AiJobCreateInput, requestOptions: AuthRequestOptions = {}): Promise<AiJobCreateResult> {
      const payload = await requestJson(`${options.modelEngineUrl}/v1/jobs`, {
        method: 'POST',
        headers: authorizationHeaders(requestOptions),
        body: JSON.stringify({
          schema_version: input.schemaVersion ?? 'v1',
          idempotency_key: input.idempotencyKey,
          operation_kind: input.operationKind,
          request_ref: input.requestRef,
          document: input.document,
          artifacts: input.artifacts,
          runtime_context: input.runtimeContext,
        }),
      })
      return toAiJobCreateResult(payload)
    },

    async getJob(jobId: string, requestOptions: AuthRequestOptions = {}): Promise<AiJobSnapshot> {
      const payload = await requestJson(`${options.modelEngineUrl}/v1/jobs/${jobId}`, {
        method: 'GET',
        headers: authorizationHeaders(requestOptions),
      })
      return toAiJobSnapshot(payload)
    },
  }
}

async function requestJson(url: string, init: RequestInit): Promise<JsonObject> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  headers.set('Accept', 'application/json')

  const response = await fetch(url, {
    ...init,
    headers,
  })
  const rawText = await response.text()
  const payload = parseJsonObject(rawText)
  if (!response.ok) {
    throw new BackendError(extractError(payload, response.statusText))
  }
  return payload
}

function parseJsonObject(rawText: string): JsonObject {
  if (!rawText.trim()) {
    return {}
  }
  const parsed = JSON.parse(rawText) as unknown
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new BackendError({
      code: 'invalid_response',
      message: 'Expected a JSON object response',
      retryable: true,
      details: null,
    })
  }
  return parsed as JsonObject
}

function extractError(payload: JsonObject, fallbackMessage: string): EngineError {
  const maybeEnvelope = payload.error
  if (maybeEnvelope && typeof maybeEnvelope === 'object' && !Array.isArray(maybeEnvelope)) {
    const error = maybeEnvelope as JsonObject
    return {
      code: String(error.code ?? 'backend_error'),
      message: String(error.message ?? fallbackMessage),
      retryable: Boolean(error.retryable ?? false),
      details: toDetailsRecord(error.details),
    }
  }

  return {
    code: 'backend_error',
    message: fallbackMessage,
    retryable: false,
    details: null,
  }
}

function authorizationHeaders(options: AuthRequestOptions): HeadersInit {
  if (!options.sessionKey) {
    return {}
  }
  return {
    Authorization: `Bearer ${options.sessionKey}`,
  }
}

function toLoginResult(payload: JsonObject): LoginResult {
  return {
    sessionKey: String(payload.session_key),
    expiresIn: Number(payload.expires_in),
    ...toCurrentSessionInfo(payload),
  }
}

function toCurrentSessionInfo(payload: JsonObject): CurrentSessionInfo {
  const user = asObject(payload.user, 'user')
  return {
    user: {
      id: String(user.id),
      email: String(user.email),
      nickname: String(user.nickname),
      status: String(user.status),
      createdAt: String(user.created_at),
    },
    creditBalance: Number(payload.credit_balance),
    reservedUnits: Number(payload.reserved_units),
  }
}

function toAiJobCreateResult(payload: JsonObject): AiJobCreateResult {
  return {
    jobId: String(payload.job_id),
    pipelineId: String(payload.pipeline_id),
    status: String(payload.status) as AiJobCreateResult['status'],
    operationKind: String(payload.operation_kind) as AiJobCreateResult['operationKind'],
    requestRef: String(payload.request_ref),
    statusUrl: String(payload.status_url),
  }
}

function toAiJobSnapshot(payload: JsonObject): AiJobSnapshot {
  return {
    jobId: String(payload.job_id),
    pipelineId: String(payload.pipeline_id),
    status: String(payload.status) as AiJobSnapshot['status'],
    operationKind: String(payload.operation_kind) as AiJobSnapshot['operationKind'],
    requestRef: String(payload.request_ref),
    document: asObject(payload.document, 'document'),
    artifacts: asObject(payload.artifacts, 'artifacts') as Record<string, Record<string, unknown>>,
    stageReports: Array.isArray(payload.stage_reports)
      ? payload.stage_reports.map((item) => asObject(item, 'stage_reports'))
      : [],
    error: payload.error && typeof payload.error === 'object' && !Array.isArray(payload.error)
      ? extractError({ error: payload.error as JsonObject }, 'backend_error')
      : null,
  }
}

function asObject(value: unknown, fieldName: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new BackendError({
      code: 'invalid_response',
      message: `Expected ${fieldName} to be an object`,
      retryable: true,
      details: null,
    })
  }
  return value as Record<string, unknown>
}

function toDetailsRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}
