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
  FilesBackend,
  LoginInput,
  LoginResult,
  PageSnapshotPayload,
  PageSummaryDto,
  ProjectCreateInput,
  ProjectDto,
  ProjectPatchInput,
  TransportArtifactDescriptor,
  TransportDocument,
  TransportStageReport,
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
    files: createRealFilesBackend(options),
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

  let response: Response
  try {
    response = await fetch(url, {
      ...init,
      headers,
    })
  } catch (error) {
    throw new BackendError({
      code: 'backend_unreachable',
      message: error instanceof Error ? error.message : 'Network request failed',
      retryable: true,
      details: null,
    })
  }
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
  let parsed: unknown
  try {
    parsed = JSON.parse(rawText) as unknown
  } catch {
    throw new BackendError({
      code: 'invalid_response',
      message: 'Expected a JSON object response',
      retryable: true,
      details: null,
    })
  }
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
    document: asObject(payload.document, 'document') as TransportDocument,
    artifacts: asObject(payload.artifacts, 'artifacts') as Record<string, TransportArtifactDescriptor>,
    stageReports: Array.isArray(payload.stage_reports)
      ? payload.stage_reports.map((item) => asObject(item, 'stage_reports') as TransportStageReport)
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

// --- FilesBackend (real implementation) ---

export function createRealFilesBackend(options: RealBackendOptions): FilesBackend {
  const base = options.serviceEngineUrl

  return {
    async listProjects(opts: AuthRequestOptions): Promise<ProjectDto[]> {
      const payload = await requestJson(`${base}/api/v1/projects`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${ensureSessionKey(opts.sessionKey)}` },
      })
      const items = Array.isArray(payload.items) ? payload.items : []
      return items.map((item) => toProjectDto(asObject(item, 'project')))
    },

    async getProject(projectId: string, opts: AuthRequestOptions): Promise<ProjectDto> {
      const payload = await requestJson(`${base}/api/v1/projects/${projectId}`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${ensureSessionKey(opts.sessionKey)}` },
      })
      return toProjectDto(payload)
    },

    async createProject(input: ProjectCreateInput, opts: AuthRequestOptions): Promise<ProjectDto> {
      const payload = await requestJson(`${base}/api/v1/projects`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${ensureSessionKey(opts.sessionKey)}` },
        body: JSON.stringify({
          id: input.id,
          name: input.name,
          source_lang: input.sourceLang,
          target_lang: input.targetLang,
          status: input.status,
          folder: input.folder,
          config: input.config,
          thumbnail_url: input.thumbnailUrl,
        }),
      })
      return toProjectDto(payload)
    },

    async updateProject(projectId: string, patch: ProjectPatchInput, opts: AuthRequestOptions): Promise<ProjectDto> {
      const body: Record<string, unknown> = {}
      if (patch.name !== undefined) body.name = patch.name
      if (patch.thumbnailUrl !== undefined) body.thumbnail_url = patch.thumbnailUrl
      if (patch.sourceLang !== undefined) body.source_lang = patch.sourceLang
      if (patch.targetLang !== undefined) body.target_lang = patch.targetLang
      if (patch.status !== undefined) body.status = patch.status
      if (patch.folder !== undefined) body.folder = patch.folder
      if (patch.config !== undefined) body.config = patch.config

      const payload = await requestJson(`${base}/api/v1/projects/${projectId}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${ensureSessionKey(opts.sessionKey)}` },
        body: JSON.stringify(body),
      })
      return toProjectDto(payload)
    },

    async deleteProject(projectId: string, opts: AuthRequestOptions): Promise<void> {
      await requestJson(`${base}/api/v1/projects/${projectId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${ensureSessionKey(opts.sessionKey)}` },
      })
    },

    async listPageSummaries(projectId: string, opts: AuthRequestOptions): Promise<PageSummaryDto[]> {
      const payload = await requestJson(`${base}/api/v1/projects/${projectId}/pages`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${ensureSessionKey(opts.sessionKey)}` },
      })
      const items = Array.isArray(payload.items) ? payload.items : []
      return items.map((item) => toPageSummaryDto(asObject(item, 'page_summary')))
    },

    async createPage(projectId: string, snapshot: PageSnapshotPayload, opts: AuthRequestOptions): Promise<PageSummaryDto> {
      const formData = buildSnapshotMultipart(snapshot)
      const response = await fetchWithAuth(`${base}/api/v1/projects/${projectId}/pages`, {
        method: 'POST',
        body: formData,
      }, ensureSessionKey(opts.sessionKey))
      const payload = await parseJsonResponse(response)
      return toPageSummaryDto(asObject(payload.page, 'page'))
    },

    async savePageSnapshot(pageId: string, snapshot: PageSnapshotPayload, opts: AuthRequestOptions): Promise<PageSummaryDto> {
      const formData = buildSnapshotMultipart(snapshot)
      const response = await fetchWithAuth(`${base}/api/v1/pages/${pageId}/snapshot`, {
        method: 'PUT',
        body: formData,
      }, ensureSessionKey(opts.sessionKey))
      const payload = await parseJsonResponse(response)
      return toPageSummaryDto(asObject(payload.page, 'page'))
    },

    async getPageSnapshot(pageId: string, opts: AuthRequestOptions): Promise<PageSnapshotPayload> {
      const response = await fetchWithAuth(`${base}/api/v1/pages/${pageId}/snapshot`, {
        method: 'GET',
      }, ensureSessionKey(opts.sessionKey))
      if (!response.ok) {
        const text = await response.text()
        const errorPayload = parseJsonObject(text)
        throw new BackendError(extractError(errorPayload, response.statusText))
      }
      return parseMultipartMixed(response)
    },

    async deletePage(pageId: string, opts: AuthRequestOptions): Promise<void> {
      await requestJson(`${base}/api/v1/pages/${pageId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${ensureSessionKey(opts.sessionKey)}` },
      })
    },

    async getPageThumbnail(pageId: string, opts: AuthRequestOptions): Promise<Blob> {
      return requestBlob(`${base}/api/v1/pages/${pageId}/thumbnail`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${ensureSessionKey(opts.sessionKey)}` },
      })
    },
  }
}

async function fetchWithAuth(url: string, init: RequestInit, sessionKey: string): Promise<Response> {
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${sessionKey}`)
  try {
    return await fetch(url, { ...init, headers })
  } catch (error) {
    throw new BackendError({
      code: 'backend_unreachable',
      message: error instanceof Error ? error.message : 'Network request failed',
      retryable: true,
      details: null,
    })
  }
}

async function parseJsonResponse(response: Response): Promise<JsonObject> {
  const rawText = await response.text()
  const payload = parseJsonObject(rawText)
  if (!response.ok) {
    throw new BackendError(extractError(payload, response.statusText))
  }
  return payload
}

async function requestBlob(url: string, init: RequestInit): Promise<Blob> {
  let response: Response
  try {
    response = await fetch(url, init)
  } catch (error) {
    throw new BackendError({
      code: 'backend_unreachable',
      message: error instanceof Error ? error.message : 'Network request failed',
      retryable: true,
      details: null,
    })
  }
  if (!response.ok) {
    const rawText = await response.text()
    const payload = parseJsonObject(rawText)
    throw new BackendError(extractError(payload, response.statusText))
  }
  return response.blob()
}

function buildSnapshotMultipart(payload: PageSnapshotPayload): FormData {
  const formData = new FormData()
  const metaJson = toSnapshotMetaJson(payload.metadata)
  formData.append('metadata', new Blob([JSON.stringify(metaJson)], { type: 'application/json' }))
  formData.append('original_image', payload.originalImage)
  formData.append('layer_blob', payload.layerBlob)
  formData.append('thumbnail', payload.thumbnail)
  return formData
}

function toSnapshotMetaJson(meta: PageSnapshotPayload['metadata']): unknown {
  return {
    page: {
      id: meta.page.id,
      project_id: meta.page.projectId,
      index: meta.page.index,
      status: meta.page.status,
      text_blocks: meta.page.textBlocks.map((tb) => ({
        id: tb.id,
        page_id: tb.pageId,
        bbox: { x: tb.bbox.x, y: tb.bbox.y, width: tb.bbox.width, height: tb.bbox.height },
        original: tb.original,
        translated: tb.translated,
        font: tb.font,
        font_size: tb.fontSize,
        color: tb.color,
        status: tb.status,
      })),
    },
  }
}

export async function parseMultipartMixed(response: Response): Promise<PageSnapshotPayload> {
  const contentType = response.headers.get('Content-Type') || ''
  const boundaryMatch = contentType.match(/boundary=(?:"([^"]+)"|([^\s;]+))/)
  if (!boundaryMatch) {
    throw new BackendError({
      code: 'invalid_response',
      message: 'Missing boundary in multipart/mixed response',
      retryable: false,
      details: null,
    })
  }
  const boundary = boundaryMatch[1] || boundaryMatch[2]

  const buffer = await response.arrayBuffer()
  const bytes = new Uint8Array(buffer)

  // Find boundary delimiters and parse parts
  const boundaryBytes = new TextEncoder().encode(`--${boundary}`)
  const parts = splitMultipartParts(bytes, boundaryBytes)

  const partMap: Record<string, { headers: Record<string, string>; body: Uint8Array }> = {}
  for (const part of parts) {
    const { headers, body } = parsePartHeadersAndBody(part)
    const disposition = headers['content-disposition'] || ''
    const nameMatch = disposition.match(/name="([^"]+)"/)
    if (nameMatch) {
      partMap[nameMatch[1]] = { headers, body }
    }
  }

  // Parse metadata
  if (!partMap['metadata']) {
    throw new BackendError({
      code: 'invalid_response',
      message: 'Missing metadata part in multipart response',
      retryable: false,
      details: null,
    })
  }
  const metaText = new TextDecoder().decode(partMap['metadata'].body)
  const metaJson = JSON.parse(metaText) as { page: Record<string, unknown> }
  const page = metaJson.page

  const textBlocksRaw = Array.isArray(page.text_blocks) ? page.text_blocks : []
  const metadata: PageSnapshotPayload['metadata'] = {
    page: {
      id: String(page.id),
      projectId: String(page.project_id),
      index: Number(page.index),
      status: String(page.status),
      textBlocks: textBlocksRaw.map((tb: Record<string, unknown>) => {
        const bbox = tb.bbox as Record<string, number>
        return {
          id: String(tb.id),
          pageId: String(tb.page_id),
          bbox: { x: bbox.x, y: bbox.y, width: bbox.width, height: bbox.height },
          original: String(tb.original),
          translated: String(tb.translated),
          font: String(tb.font),
          fontSize: Number(tb.font_size),
          color: String(tb.color),
          status: String(tb.status),
        }
      }),
    },
  }

  const toBlobPart = (name: string, fallbackType: string): Blob => {
    const p = partMap[name]
    if (!p) {
      throw new BackendError({
        code: 'invalid_response',
        message: `Missing ${name} part in multipart response`,
        retryable: false,
        details: null,
      })
    }
    const type = p.headers['content-type'] || fallbackType
    return new Blob([p.body], { type })
  }

  return {
    metadata,
    originalImage: toBlobPart('original_image', 'image/png'),
    layerBlob: toBlobPart('layer_blob', 'application/octet-stream'),
    thumbnail: toBlobPart('thumbnail', 'image/png'),
  }
}

function splitMultipartParts(data: Uint8Array, boundaryBytes: Uint8Array): Uint8Array[] {
  const parts: Uint8Array[] = []
  const indices: number[] = []

  // Find all boundary positions
  for (let i = 0; i <= data.length - boundaryBytes.length; i++) {
    let match = true
    for (let j = 0; j < boundaryBytes.length; j++) {
      if (data[i + j] !== boundaryBytes[j]) {
        match = false
        break
      }
    }
    if (match) {
      indices.push(i)
    }
  }

  // Extract content between boundaries
  for (let i = 0; i < indices.length - 1; i++) {
    const start = indices[i] + boundaryBytes.length
    const end = indices[i + 1]
    // Skip leading \r\n after boundary
    let contentStart = start
    if (data[contentStart] === 0x0d && data[contentStart + 1] === 0x0a) {
      contentStart += 2
    }
    // Skip trailing \r\n before next boundary
    let contentEnd = end
    if (data[contentEnd - 2] === 0x0d && data[contentEnd - 1] === 0x0a) {
      contentEnd -= 2
    }
    if (contentStart < contentEnd) {
      parts.push(data.slice(contentStart, contentEnd))
    }
  }

  return parts
}

function parsePartHeadersAndBody(part: Uint8Array): { headers: Record<string, string>; body: Uint8Array } {
  // Find the \r\n\r\n separator between headers and body
  let separatorIdx = -1
  for (let i = 0; i < part.length - 3; i++) {
    if (part[i] === 0x0d && part[i + 1] === 0x0a && part[i + 2] === 0x0d && part[i + 3] === 0x0a) {
      separatorIdx = i
      break
    }
  }

  if (separatorIdx === -1) {
    return { headers: {}, body: part }
  }

  const headerText = new TextDecoder().decode(part.slice(0, separatorIdx))
  const body = part.slice(separatorIdx + 4)
  const headers: Record<string, string> = {}
  for (const line of headerText.split('\r\n')) {
    const colonIdx = line.indexOf(':')
    if (colonIdx > 0) {
      headers[line.substring(0, colonIdx).trim().toLowerCase()] = line.substring(colonIdx + 1).trim()
    }
  }
  return { headers, body }
}

function toProjectDto(json: Record<string, unknown>): ProjectDto {
  return {
    id: String(json.id),
    name: String(json.name),
    thumbnailUrl: json.thumbnail_url != null ? String(json.thumbnail_url) : null,
    sourceLang: String(json.source_lang),
    targetLang: String(json.target_lang),
    pageCount: Number(json.page_count ?? 0),
    status: String(json.status),
    folder: String(json.folder ?? ''),
    config: (json.config && typeof json.config === 'object' && !Array.isArray(json.config)) ? json.config as Record<string, unknown> : {},
    createdAt: String(json.created_at),
    updatedAt: String(json.updated_at),
  }
}

function toPageSummaryDto(json: Record<string, unknown>): PageSummaryDto {
  return {
    id: String(json.id),
    projectId: String(json.project_id),
    index: Number(json.index),
    status: String(json.status),
    thumbnailUrl: json.thumbnail_url != null ? String(json.thumbnail_url) : null,
    updatedAt: String(json.updated_at),
  }
}
