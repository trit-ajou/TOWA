import type {
  AiJobCreateInput,
  AiJobCreateResult,
  AiJobSnapshot,
  AiJobsBackend,
  AppBackend,
  AuthBackend,
  AuthRequestOptions,
  CurrentSessionInfo,
  FilesBackend,
  LoginInput,
  LoginResult,
  PageSnapshotPayload,
  PageSummaryDto,
  ProjectCreateInput,
  ProjectDto,
  ProjectPatchInput,
  TransportArtifactDescriptor,
  TransportDocumentPatch,
  TransportStageReport,
} from './contracts'
import { BackendError, ensureSessionKey } from './errors'

interface EmulatedJobRecord {
  jobId: string
  pipelineId: string
  ownerScope: string
  idempotencyKey: string
  requestFingerprint: string
  mode: AiJobCreateInput['runtimeContext']['mode']
  operationKind: EmulatedOperationKind
  requestRef: string
  document: AiJobCreateInput['document']
  artifacts: Record<string, TransportArtifactDescriptor>
  documentPatch: TransportDocumentPatch
  pollCount: number
}

interface EmulatedSessionRecord extends LoginResult {}

type EmulatedOperationKind = Exclude<AiJobCreateInput['operationKind'], 'pipeline'>

const OPERATION_STAGE_NAMES = {
  detect: ['text_detection'],
  inpaint: ['text_detection', 'mask_or_erase_planning', 'inpaint'],
  translate: ['text_detection', 'ocr', 'translation'],
} as const

const OPERATION_META_KEYS = {
  detect: 'text_detection',
  inpaint: 'inpaint',
  translate: 'translation',
} as const

export function createEmulatedAppBackend(): AppBackend {
  const sessions = new Map<string, EmulatedSessionRecord>()
  const jobs = new Map<string, EmulatedJobRecord>()
  const artifactBlobs = new Map<string, Map<string, Blob>>()
  const jobIdsByScopedIdempotencyKey = new Map<string, string>()
  let sessionSequence = 1
  let jobSequence = 1
  let pipelineSequence = 1

  const auth: AuthBackend = {
    async devLogin(input: LoginInput): Promise<LoginResult> {
      const normalizedEmail = input.email.trim().toLowerCase()
      const nickname = input.nickname?.trim() || normalizedEmail.split('@')[0] || 'tester'
      const sessionKey = `emu-session-${sessionSequence++}`
      const payload: LoginResult = {
        sessionKey,
        expiresIn: 24 * 60 * 60,
        user: {
          id: `emu-user-${normalizedEmail.replace(/[^a-z0-9]+/gi, '-')}`,
          email: normalizedEmail,
          nickname,
          status: 'active',
          createdAt: '2026-03-25T00:00:00Z',
        },
        creditBalance: 1000,
        reservedUnits: 0,
      }
      sessions.set(sessionKey, payload)
      return clone(payload)
    },

    async getCurrentUser(options: AuthRequestOptions): Promise<CurrentSessionInfo> {
      const sessionKey = ensureSessionKey(options.sessionKey)
      const payload = sessions.get(sessionKey)
      if (!payload) {
        throw new BackendError({
          code: 'session_invalid',
          message: 'Unknown emulated session',
          retryable: false,
          details: null,
        })
      }
      return clone({
        user: payload.user,
        creditBalance: payload.creditBalance,
        reservedUnits: payload.reservedUnits,
      })
    },
  }

  const aiJobs: AiJobsBackend = {
    async createJob(input: AiJobCreateInput, options: AuthRequestOptions = {}): Promise<AiJobCreateResult> {
      if (input.operationKind === 'pipeline') {
        throw new BackendError({
          code: 'model_validation_error',
          message: 'Unsupported operation_kind: pipeline',
          retryable: false,
          details: null,
        })
      }

      const ownerScope = toOwnerScope(input, options)
      const requestFingerprint = toRequestFingerprint(input)
      const scopedKey = `${ownerScope}::${input.idempotencyKey}`
      const existingJobId = jobIdsByScopedIdempotencyKey.get(scopedKey)
      if (existingJobId) {
        const existing = jobs.get(existingJobId)
        if (!existing) {
          jobIdsByScopedIdempotencyKey.delete(scopedKey)
        } else {
          if (existing.requestFingerprint !== requestFingerprint) {
            throw new BackendError({
              code: 'model_job_conflict',
              message: 'idempotencyKey cannot be reused with a different request payload',
              retryable: false,
              details: { reason: 'idempotency_payload_mismatch' },
            })
          }
          return {
            jobId: existing.jobId,
            pipelineId: existing.pipelineId,
            status: existing.pollCount > 1 ? 'succeeded' : existing.pollCount > 0 ? 'running' : 'queued',
            operationKind: existing.operationKind,
            requestRef: existing.requestRef,
            statusUrl: `/v1/jobs/${existing.jobId}`,
          }
        }
      }

      const jobId = `emu-job-${jobSequence++}`
      const pipelineId = `emu-pipe-${pipelineSequence++}`
      const artifacts = withPrimaryBitmapArtifact(input)
      const blobs = new Map<string, Blob>()
      blobs.set('artifact://input/primary_bitmap', input.primaryBitmap)
      jobs.set(jobId, {
        jobId,
        pipelineId,
        ownerScope,
        idempotencyKey: input.idempotencyKey,
        requestFingerprint,
        mode: input.runtimeContext.mode,
        operationKind: input.operationKind,
        requestRef: input.requestRef,
        document: clone(input.document),
        artifacts: clone(artifacts),
        documentPatch: { patches: [] },
        pollCount: 0,
      })
      artifactBlobs.set(jobId, blobs)
      jobIdsByScopedIdempotencyKey.set(scopedKey, jobId)

      return {
        jobId,
        pipelineId,
        status: 'queued',
        operationKind: input.operationKind,
        requestRef: input.requestRef,
        statusUrl: `/v1/jobs/${jobId}`,
      }
    },

    async getJob(jobId: string, options: AuthRequestOptions = {}): Promise<AiJobSnapshot> {
      const record = jobs.get(jobId)
      if (!record) {
        throw new BackendError({
          code: 'model_job_not_found',
          message: `Unknown job_id: ${jobId}`,
          retryable: false,
          details: null,
        })
      }
      assertCanReadJob(record, options)

      record.pollCount += 1
      if (record.pollCount === 1) {
        return {
          jobId: record.jobId,
          pipelineId: record.pipelineId,
          status: 'running',
          operationKind: record.operationKind,
          requestRef: record.requestRef,
          document: clone(record.document),
          documentPatch: clone(record.documentPatch),
          artifacts: clone(record.artifacts),
          stageReports: [],
          error: null,
        }
      }

      const document = clone(record.document)
      const metaKey = OPERATION_META_KEYS[record.operationKind]
      const stageReports: TransportStageReport[] = OPERATION_STAGE_NAMES[record.operationKind].map((stageName, index) => ({
        stage_name: stageName,
        stage_run_id: `${record.pipelineId}:${stageName}:${index + 1}`,
        status: 'succeeded',
        metrics: {
          executor: 'emulated',
          operation_kind: record.operationKind,
        },
      }))
      document.stage_meta = {
        ...(typeof document.stage_meta === 'object' && document.stage_meta ? document.stage_meta : {}),
        [metaKey]: {
          status: 'done',
          executor: 'emulated',
          pipeline_id: record.pipelineId,
        },
      }
      const documentPatch = buildTerminalDocumentPatch(record)
      const artifacts = buildTerminalArtifacts(record)
      if (record.operationKind === 'inpaint') {
        artifactBlobs.get(record.jobId)?.set(
          `artifact://emu/${record.jobId}/inpaint.png`,
          tinyPngBlob(),
        )
      }
      record.documentPatch = documentPatch
      record.artifacts = artifacts

      return {
        jobId: record.jobId,
        pipelineId: record.pipelineId,
        status: 'succeeded',
        operationKind: record.operationKind,
        requestRef: record.requestRef,
        document,
        documentPatch: clone(documentPatch),
        artifacts: clone(artifacts),
        stageReports,
        error: null,
      }
    },

    async getArtifact(
      jobId: string,
      artifactRef: string,
      options: AuthRequestOptions = {},
    ): Promise<Blob> {
      const record = jobs.get(jobId)
      if (!record) {
        throw new BackendError({
          code: 'model_job_not_found',
          message: `Unknown job_id: ${jobId}`,
          retryable: false,
          details: null,
        })
      }
      assertCanReadJob(record, options)
      if (!record.artifacts[artifactRef]) {
        throw new BackendError({
          code: 'model_artifact_not_found',
          message: `Unknown artifact_ref for job ${jobId}: ${artifactRef}`,
          retryable: false,
          details: { artifact_ref: artifactRef },
        })
      }
      const blob = artifactBlobs.get(jobId)?.get(artifactRef)
      if (!blob) {
        throw new BackendError({
          code: 'model_artifact_not_found',
          message: `Artifact binary does not exist for ref: ${artifactRef}`,
          retryable: false,
          details: { artifact_ref: artifactRef },
        })
      }
      return blob
    },
  }

  const files: FilesBackend = createEmulatedFilesBackend()

  return { auth, aiJobs, files }
}

// --- FilesBackend emulated (in-memory implementation) ---

interface EmulatedPageRecord {
  // summary fields
  id: string
  projectId: string
  index: number
  status: string
  updatedAt: string
  // snapshot payload
  metadata: PageSnapshotPayload['metadata']
  originalImage: Blob
  layerBlob: Blob
  thumbnail: Blob
}

export function createEmulatedFilesBackend(): FilesBackend {
  const projects = new Map<string, ProjectDto>()
  const pages = new Map<string, EmulatedPageRecord>()
  const pagesByProject = new Map<string, string[]>()

  function getPageCount(projectId: string): number {
    return (pagesByProject.get(projectId) || []).length
  }

  function toSummary(record: EmulatedPageRecord): PageSummaryDto {
    return {
      id: record.id,
      projectId: record.projectId,
      index: record.index,
      status: record.status,
      thumbnailUrl: null,
      updatedAt: record.updatedAt,
    }
  }

  return {
    async listProjects(opts: AuthRequestOptions): Promise<ProjectDto[]> {
      ensureSessionKey(opts.sessionKey)
      return Array.from(projects.values()).map((p) => clone(p))
    },

    async getProject(projectId: string, opts: AuthRequestOptions): Promise<ProjectDto> {
      ensureSessionKey(opts.sessionKey)
      const project = projects.get(projectId)
      if (!project) {
        throw new BackendError({
          code: 'project_not_found',
          message: `Project ${projectId} not found`,
          retryable: false,
          details: null,
        })
      }
      return clone({ ...project, pageCount: getPageCount(projectId) })
    },

    async createProject(input: ProjectCreateInput, opts: AuthRequestOptions): Promise<ProjectDto> {
      ensureSessionKey(opts.sessionKey)
      if (projects.has(input.id)) {
        throw new BackendError({
          code: 'project_conflict',
          message: `Project ${input.id} already exists`,
          retryable: false,
          details: null,
        })
      }
      const now = new Date().toISOString()
      const project: ProjectDto = {
        id: input.id,
        name: input.name,
        thumbnailUrl: input.thumbnailUrl ?? null,
        sourceLang: input.sourceLang,
        targetLang: input.targetLang,
        pageCount: 0,
        status: input.status ?? 'todo',
        folder: input.folder ?? '',
        config: input.config ?? {},
        createdAt: now,
        updatedAt: now,
      }
      projects.set(input.id, project)
      pagesByProject.set(input.id, [])
      return clone(project)
    },

    async updateProject(projectId: string, patch: ProjectPatchInput, opts: AuthRequestOptions): Promise<ProjectDto> {
      ensureSessionKey(opts.sessionKey)
      const project = projects.get(projectId)
      if (!project) {
        throw new BackendError({
          code: 'project_not_found',
          message: `Project ${projectId} not found`,
          retryable: false,
          details: null,
        })
      }
      if (patch.name !== undefined) project.name = patch.name
      if (patch.thumbnailUrl !== undefined) project.thumbnailUrl = patch.thumbnailUrl ?? null
      if (patch.sourceLang !== undefined) project.sourceLang = patch.sourceLang
      if (patch.targetLang !== undefined) project.targetLang = patch.targetLang
      if (patch.status !== undefined) project.status = patch.status
      if (patch.folder !== undefined) project.folder = patch.folder
      if (patch.config !== undefined) project.config = patch.config
      project.updatedAt = new Date().toISOString()
      project.pageCount = getPageCount(projectId)
      return clone(project)
    },

    async deleteProject(projectId: string, opts: AuthRequestOptions): Promise<void> {
      ensureSessionKey(opts.sessionKey)
      if (!projects.has(projectId)) {
        throw new BackendError({
          code: 'project_not_found',
          message: `Project ${projectId} not found`,
          retryable: false,
          details: null,
        })
      }
      // Delete all pages belonging to this project
      const pageIds = pagesByProject.get(projectId) || []
      for (const pid of pageIds) {
        pages.delete(pid)
      }
      pagesByProject.delete(projectId)
      projects.delete(projectId)
    },

    async listPageSummaries(projectId: string, opts: AuthRequestOptions): Promise<PageSummaryDto[]> {
      ensureSessionKey(opts.sessionKey)
      const pageIds = pagesByProject.get(projectId)
      if (!pageIds) {
        throw new BackendError({
          code: 'project_not_found',
          message: `Project ${projectId} not found`,
          retryable: false,
          details: null,
        })
      }
      return pageIds.map((pid) => {
        const record = pages.get(pid)!
        return toSummary(record)
      })
    },

    async createPage(projectId: string, snapshot: PageSnapshotPayload, opts: AuthRequestOptions): Promise<PageSummaryDto> {
      ensureSessionKey(opts.sessionKey)
      const pageIds = pagesByProject.get(projectId)
      if (!pageIds) {
        throw new BackendError({
          code: 'project_not_found',
          message: `Project ${projectId} not found`,
          retryable: false,
          details: null,
        })
      }
      const pageId = snapshot.metadata.page.id
      if (pages.has(pageId)) {
        throw new BackendError({
          code: 'page_conflict',
          message: `Page ${pageId} already exists`,
          retryable: false,
          details: null,
        })
      }
      const expectedIndex = pageIds.length + 1
      if (snapshot.metadata.page.index !== expectedIndex) {
        throw new BackendError({
          code: 'page_conflict',
          message: `Expected index ${expectedIndex}, got ${snapshot.metadata.page.index}`,
          retryable: false,
          details: { reason: 'index_invalid' },
        })
      }
      const now = new Date().toISOString()
      const record: EmulatedPageRecord = {
        id: pageId,
        projectId,
        index: snapshot.metadata.page.index,
        status: snapshot.metadata.page.status,
        updatedAt: now,
        metadata: clone(snapshot.metadata),
        originalImage: snapshot.originalImage,
        layerBlob: snapshot.layerBlob,
        thumbnail: snapshot.thumbnail,
      }
      pages.set(pageId, record)
      pageIds.push(pageId)
      // Update project pageCount
      const project = projects.get(projectId)
      if (project) {
        project.pageCount = getPageCount(projectId)
        project.updatedAt = now
      }
      return toSummary(record)
    },

    async savePageSnapshot(pageId: string, snapshot: PageSnapshotPayload, opts: AuthRequestOptions): Promise<PageSummaryDto> {
      ensureSessionKey(opts.sessionKey)
      const existing = pages.get(pageId)
      if (!existing) {
        throw new BackendError({
          code: 'page_not_found',
          message: `Page ${pageId} not found`,
          retryable: false,
          details: null,
        })
      }
      const now = new Date().toISOString()
      existing.status = snapshot.metadata.page.status
      existing.updatedAt = now
      existing.metadata = clone(snapshot.metadata)
      existing.originalImage = snapshot.originalImage
      existing.layerBlob = snapshot.layerBlob
      existing.thumbnail = snapshot.thumbnail
      return toSummary(existing)
    },

    async getPageSnapshot(pageId: string, opts: AuthRequestOptions): Promise<PageSnapshotPayload> {
      ensureSessionKey(opts.sessionKey)
      const record = pages.get(pageId)
      if (!record) {
        throw new BackendError({
          code: 'page_not_found',
          message: `Page ${pageId} not found`,
          retryable: false,
          details: null,
        })
      }
      return {
        metadata: clone(record.metadata),
        originalImage: record.originalImage,
        layerBlob: record.layerBlob,
        thumbnail: record.thumbnail,
      }
    },

    async deletePage(pageId: string, opts: AuthRequestOptions): Promise<void> {
      ensureSessionKey(opts.sessionKey)
      const record = pages.get(pageId)
      if (!record) {
        throw new BackendError({
          code: 'page_not_found',
          message: `Page ${pageId} not found`,
          retryable: false,
          details: null,
        })
      }
      const projectId = record.projectId
      pages.delete(pageId)
      // Remove from pagesByProject and reindex
      const pageIds = pagesByProject.get(projectId)
      if (pageIds) {
        const idx = pageIds.indexOf(pageId)
        if (idx !== -1) {
          pageIds.splice(idx, 1)
        }
        // Reindex remaining pages to 1..N
        for (let i = 0; i < pageIds.length; i++) {
          const p = pages.get(pageIds[i])!
          p.index = i + 1
          p.metadata.page.index = i + 1
        }
      }
      // Update project pageCount
      const project = projects.get(projectId)
      if (project) {
        project.pageCount = getPageCount(projectId)
        project.updatedAt = new Date().toISOString()
      }
    },

    async getPageThumbnail(pageId: string, opts: AuthRequestOptions): Promise<Blob> {
      ensureSessionKey(opts.sessionKey)
      const record = pages.get(pageId)
      if (!record) {
        throw new BackendError({
          code: 'page_not_found',
          message: `Page ${pageId} not found`,
          retryable: false,
          details: null,
        })
      }
      return record.thumbnail
    },
  }
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function withPrimaryBitmapArtifact(input: AiJobCreateInput): Record<string, TransportArtifactDescriptor> {
  return {
    ...(input.artifacts ?? {}),
    'artifact://input/primary_bitmap': {
      artifact_ref: 'artifact://input/primary_bitmap',
      kind: 'bitmap',
      media_type: input.primaryBitmap.type || 'image/png',
      uri: 'emu://input/primary_bitmap',
      byte_size: input.primaryBitmap.size,
      version: 1,
      status: 'ready',
      metadata: { upload_part: 'primary_bitmap' },
    },
  }
}

function assertCanReadJob(record: EmulatedJobRecord, options: AuthRequestOptions): void {
  if (record.mode !== 'saas') {
    return
  }
  const sessionKey = options.sessionKey?.trim()
  if (!sessionKey) {
    throw new BackendError({
      code: 'session_key_required',
      message: 'sessionKey is required for this request',
      retryable: false,
      details: null,
    })
  }
  if (`saas:${sessionKey}` !== record.ownerScope) {
    throw new BackendError({
      code: 'model_job_not_found',
      message: `Unknown job_id: ${record.jobId}`,
      retryable: false,
      details: null,
    })
  }
}

function buildTerminalArtifacts(record: EmulatedJobRecord): Record<string, TransportArtifactDescriptor> {
  const artifacts = clone(record.artifacts)
  if (record.operationKind !== 'inpaint') {
    return artifacts
  }

  const artifactRef = `artifact://emu/${record.jobId}/inpaint.png`
  artifacts[artifactRef] = {
    artifact_ref: artifactRef,
    kind: 'bitmap',
    media_type: 'image/png',
    uri: `emu://jobs/${record.jobId}/inpaint.png`,
    version: 1,
    status: 'ready',
    metadata: { executor: 'emulated' },
  }
  return artifacts
}

function buildTerminalDocumentPatch(record: EmulatedJobRecord): TransportDocumentPatch {
  const metaKey = OPERATION_META_KEYS[record.operationKind]
  const patches: TransportDocumentPatch['patches'] = []

  if (record.operationKind === 'detect' || record.operationKind === 'translate') {
    patches.push({
      op: 'replace_text_blocks',
      payload: { text_blocks: emulatedTextBlocks(record) },
    })
  }

  if (record.operationKind === 'inpaint') {
    patches.push({
      op: 'add_layer',
      payload: {
        layer: {
          id: `ai_inpaint_${record.jobId}`,
          name: 'Emulated Inpaint',
          type: 'graphic',
          left: 0,
          top: 0,
          width: Number(record.document.width ?? 1),
          height: Number(record.document.height ?? 1),
          source_ref: `artifact://emu/${record.jobId}/inpaint.png`,
        },
      },
    })
  }

  patches.push({
    op: 'set_stage_meta',
    payload: {
      key: metaKey,
      value: {
        status: 'done',
        executor: 'emulated',
        pipeline_id: record.pipelineId,
      },
    },
  })

  return { patches }
}

function emulatedTextBlocks(record: EmulatedJobRecord): Record<string, unknown>[] {
  const existing = Array.isArray(record.document.text_blocks) ? record.document.text_blocks : []
  if (existing.length > 0) {
    return existing.map((block, index) => normalizeEmulatedTextBlock(block, index, record))
  }

  return [
    {
      block_id: `emu_block_${record.jobId}_1`,
      source_lang_text: 'Sample text',
      translated_text: record.operationKind === 'translate' ? '샘플 번역' : '',
      bbox: { x: 40, y: 40, width: 220, height: 80 },
      reading_order: 1,
      writing_mode: 'horizontal',
    },
  ]
}

function normalizeEmulatedTextBlock(
  block: unknown,
  index: number,
  record: EmulatedJobRecord,
): Record<string, unknown> {
  const payload = block && typeof block === 'object' && !Array.isArray(block)
    ? block as Record<string, unknown>
    : {}
  return {
    block_id: String(payload.block_id ?? payload.id ?? `emu_block_${record.jobId}_${index + 1}`),
    source_lang_text: String(payload.source_lang_text ?? payload.original ?? ''),
    translated_text: String(
      payload.translated_text
        ?? payload.translated
        ?? (record.operationKind === 'translate' ? payload.source_lang_text ?? payload.original ?? '' : ''),
    ),
    bbox: normalizeEmulatedBBox(payload.bbox),
    reading_order: Number(payload.reading_order ?? index + 1),
    writing_mode: String(payload.writing_mode ?? 'horizontal'),
  }
}

function normalizeEmulatedBBox(value: unknown): Record<string, number> {
  const payload = value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
  return {
    x: Number(payload.x ?? payload.left ?? 40),
    y: Number(payload.y ?? payload.top ?? 40),
    width: Number(payload.width ?? payload.w ?? 220),
    height: Number(payload.height ?? payload.h ?? 80),
  }
}

function tinyPngBlob(): Blob {
  return new Blob([
    new Uint8Array([
      0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
      0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
      0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
      0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4,
      0x89, 0x00, 0x00, 0x00, 0x0a, 0x49, 0x44, 0x41,
      0x54, 0x78, 0x9c, 0x63, 0x00, 0x01, 0x00, 0x00,
      0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00,
      0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae,
      0x42, 0x60, 0x82,
    ]),
  ], { type: 'image/png' })
}


function toOwnerScope(input: AiJobCreateInput, options: AuthRequestOptions): string {
  if (input.runtimeContext.mode === 'saas') {
    return `saas:${ensureSessionKey(options.sessionKey)}`
  }
  const requestedBy = input.runtimeContext.requested_by?.trim()
  return requestedBy ? `local:${requestedBy}` : 'local'
}


function toRequestFingerprint(input: AiJobCreateInput): string {
  return stableStringify({
    schemaVersion: input.schemaVersion ?? 'v1',
    operationKind: input.operationKind,
    requestRef: input.requestRef,
    document: input.document,
    artifacts: input.artifacts ?? {},
    primaryBitmap: {
      mediaType: input.primaryBitmap.type,
      byteSize: input.primaryBitmap.size,
    },
    runtimeContext: input.runtimeContext,
  })
}


function stableStringify(value: unknown): string {
  return JSON.stringify(canonicalize(value))
}


function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => canonicalize(item))
  }
  if (value && typeof value === 'object') {
    return Object.keys(value as Record<string, unknown>)
      .sort()
      .reduce<Record<string, unknown>>((acc, key) => {
        acc[key] = canonicalize((value as Record<string, unknown>)[key])
        return acc
      }, {})
  }
  return value
}
