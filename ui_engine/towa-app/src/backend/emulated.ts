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
} from './contracts'
import { BackendError, ensureSessionKey } from './errors'

interface EmulatedJobRecord {
  jobId: string
  pipelineId: string
  operationKind: AiJobCreateInput['operationKind']
  requestRef: string
  document: Record<string, unknown>
  artifacts: Record<string, Record<string, unknown>>
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
    async createJob(input: AiJobCreateInput): Promise<AiJobCreateResult> {
      if (input.operationKind === 'pipeline') {
        throw new BackendError({
          code: 'model_validation_error',
          message: 'Unsupported operation_kind: pipeline',
          retryable: false,
          details: null,
        })
      }

      const jobId = `emu-job-${jobSequence++}`
      const pipelineId = `emu-pipe-${pipelineSequence++}`
      jobs.set(jobId, {
        jobId,
        pipelineId,
        operationKind: input.operationKind,
        requestRef: input.requestRef,
        document: clone(input.document),
        artifacts: clone(input.artifacts),
        pollCount: 0,
      })

      return {
        jobId,
        pipelineId,
        status: 'queued',
        operationKind: input.operationKind,
        requestRef: input.requestRef,
        statusUrl: `/v1/jobs/${jobId}`,
      }
    },

    async getJob(jobId: string): Promise<AiJobSnapshot> {
      const record = jobs.get(jobId)
      if (!record) {
        throw new BackendError({
          code: 'model_job_not_found',
          message: `Unknown job_id: ${jobId}`,
          retryable: false,
          details: null,
        })
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
      const stageReports = OPERATION_STAGE_NAMES[record.operationKind].map((stageName, index) => ({
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
