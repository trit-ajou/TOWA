export type BackendAdapterMode = 'real' | 'emulated'
export type AiOperationKind = 'detect' | 'inpaint' | 'translate' | 'pipeline'
export type AiJobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'partial'

export interface EngineError {
  code: string
  message: string
  retryable: boolean
  details: Record<string, unknown> | null
}

export interface SessionUser {
  id: string
  email: string
  nickname: string
  status: string
  createdAt: string
}

export interface CurrentSessionInfo {
  user: SessionUser
  creditBalance: number
  reservedUnits: number
}

export interface LoginInput {
  email: string
  nickname?: string
}

export interface LoginResult extends CurrentSessionInfo {
  sessionKey: string
  expiresIn: number
}

export interface AuthRequestOptions {
  sessionKey?: string
}

export interface AiJobCreateInput {
  schemaVersion?: string
  idempotencyKey: string
  operationKind: AiOperationKind
  requestRef: string
  document: Record<string, unknown>
  artifacts: Record<string, Record<string, unknown>>
  runtimeContext: Record<string, unknown>
}

export interface AiJobCreateResult {
  jobId: string
  pipelineId: string
  status: AiJobStatus
  operationKind: AiOperationKind
  requestRef: string
  statusUrl: string
}

export interface AiJobSnapshot {
  jobId: string
  pipelineId: string
  status: AiJobStatus
  operationKind: AiOperationKind
  requestRef: string
  document: Record<string, unknown>
  artifacts: Record<string, Record<string, unknown>>
  stageReports: Array<Record<string, unknown>>
  error: EngineError | null
}

export interface AuthBackend {
  devLogin(input: LoginInput): Promise<LoginResult>
  getCurrentUser(options: AuthRequestOptions): Promise<CurrentSessionInfo>
}

export interface AiJobsBackend {
  createJob(input: AiJobCreateInput, options?: AuthRequestOptions): Promise<AiJobCreateResult>
  getJob(jobId: string, options?: AuthRequestOptions): Promise<AiJobSnapshot>
}

export interface AppBackend {
  auth: AuthBackend
  aiJobs: AiJobsBackend
}

export interface AppBackendConfig {
  authMode: BackendAdapterMode
  aiMode: BackendAdapterMode
  serviceEngineUrl: string
  modelEngineUrl: string
}
