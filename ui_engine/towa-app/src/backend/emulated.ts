import type {
  AiJobCreateInput,
  AiJobCreateResult,
  AiJobSnapshot,
  AiJobsBackend,
  AppBackend,
  AuthBackend,
  AuthRequestOptions,
  CurrentSessionInfo,
  LoginInput,
  LoginResult,
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
  operationKind: AiJobCreateInput['operationKind']
  requestRef: string
  document: AiJobCreateInput['document']
  artifacts: AiJobCreateInput['artifacts']
  pollCount: number
}

interface EmulatedSessionRecord extends LoginResult {}

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
        artifacts: clone(input.artifacts),
        pollCount: 0,
      })
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
      if (record.mode === 'saas') {
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
            message: `Unknown job_id: ${jobId}`,
            retryable: false,
            details: null,
          })
        }
      }

      record.pollCount += 1
      if (record.pollCount === 1) {
        return {
          jobId: record.jobId,
          pipelineId: record.pipelineId,
          status: 'running',
          operationKind: record.operationKind,
          requestRef: record.requestRef,
          document: clone(record.document),
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

      return {
        jobId: record.jobId,
        pipelineId: record.pipelineId,
        status: 'succeeded',
        operationKind: record.operationKind,
        requestRef: record.requestRef,
        document,
        artifacts: clone(record.artifacts),
        stageReports,
        error: null,
      }
    },
  }

  return { auth, aiJobs }
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
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
    artifacts: input.artifacts,
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
