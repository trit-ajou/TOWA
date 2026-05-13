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

export interface TransportDocument {
  id: string
  name?: string
  width?: number
  height?: number
  layers?: unknown[]
  text_blocks?: unknown[]
  stage_meta?: Record<string, unknown>
  [key: string]: unknown
}

export interface TransportArtifactDescriptor {
  artifact_ref: string
  kind: string
  media_type: string
  uri: string
  width?: number
  height?: number
  byte_size?: number
  checksum?: string
  version?: number
  producer_stage?: string
  status?: string
  expires_at?: string
  metadata?: Record<string, unknown>
  [key: string]: unknown
}

export interface TransportRuntimeContext {
  mode: 'saas' | 'local'
  workspace_uri: string
  requested_by?: string
  cancellation_token?: string
  target_regions?: unknown[]
  selected_layer_ids?: string[]
  [key: string]: unknown
}

export interface TransportStageReport {
  stage_name: string
  stage_run_id: string
  status: string
  metrics?: Record<string, unknown>
  started_at?: string
  finished_at?: string
  [key: string]: unknown
}

export interface TransportPatchOperation {
  op: string
  payload: Record<string, unknown>
  [key: string]: unknown
}

export interface TransportDocumentPatch {
  patches: TransportPatchOperation[]
  [key: string]: unknown
}

export interface AiJobCreateInput {
  schemaVersion?: string
  idempotencyKey: string
  operationKind: AiOperationKind
  requestRef: string
  document: TransportDocument
  artifacts?: Record<string, TransportArtifactDescriptor>
  primaryBitmap: Blob
  runtimeContext: TransportRuntimeContext
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
  document: TransportDocument
  documentPatch: TransportDocumentPatch
  artifacts: Record<string, TransportArtifactDescriptor>
  stageReports: TransportStageReport[]
  error: EngineError | null
}

export interface AuthBackend {
  devLogin(input: LoginInput): Promise<LoginResult>
  getCurrentUser(options: AuthRequestOptions): Promise<CurrentSessionInfo>
}

export interface AiJobsBackend {
  createJob(input: AiJobCreateInput, options?: AuthRequestOptions): Promise<AiJobCreateResult>
  getJob(jobId: string, options?: AuthRequestOptions): Promise<AiJobSnapshot>
  getArtifact(jobId: string, artifactRef: string, options?: AuthRequestOptions): Promise<Blob>
}

// --- Files backend (project/page storage, service_engine) ---

export interface ProjectDto {
  id: string
  name: string
  thumbnailUrl: string | null
  sourceLang: string
  targetLang: string
  pageCount: number
  status: string
  folder: string
  config: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

export interface PageSummaryDto {
  id: string
  projectId: string
  index: number
  status: string
  thumbnailUrl: string | null
  updatedAt: string
}

export interface PageSnapshotMetaDto {
  page: {
    id: string
    projectId: string
    index: number
    status: string
  }
}

/** Full page snapshot payload (four multipart parts). */
export interface PageSnapshotPayload {
  metadata: PageSnapshotMetaDto
  originalImage: Blob
  layerBlob: Blob
  thumbnail: Blob
}

export interface ProjectCreateInput {
  id: string
  name: string
  sourceLang: string
  targetLang: string
  status?: string
  folder?: string
  config?: Record<string, unknown>
  thumbnailUrl?: string | null
}

export type ProjectPatchInput = Partial<
  Pick<
    ProjectDto,
    'name' | 'thumbnailUrl' | 'sourceLang' | 'targetLang' | 'status' | 'folder' | 'config'
  >
>

export interface FilesBackend {
  // Project CRUD
  listProjects(options: AuthRequestOptions): Promise<ProjectDto[]>
  getProject(projectId: string, options: AuthRequestOptions): Promise<ProjectDto>
  createProject(input: ProjectCreateInput, options: AuthRequestOptions): Promise<ProjectDto>
  updateProject(projectId: string, patch: ProjectPatchInput, options: AuthRequestOptions): Promise<ProjectDto>
  deleteProject(projectId: string, options: AuthRequestOptions): Promise<void>

  // Pages (summary list)
  listPageSummaries(projectId: string, options: AuthRequestOptions): Promise<PageSummaryDto[]>

  // Pages (full snapshot)
  createPage(projectId: string, snapshot: PageSnapshotPayload, options: AuthRequestOptions): Promise<PageSummaryDto>
  savePageSnapshot(pageId: string, snapshot: PageSnapshotPayload, options: AuthRequestOptions): Promise<PageSummaryDto>
  getPageSnapshot(pageId: string, options: AuthRequestOptions): Promise<PageSnapshotPayload>
  deletePage(pageId: string, options: AuthRequestOptions): Promise<void>

  // Thumbnail (bearer-authed blob)
  getPageThumbnail(pageId: string, options: AuthRequestOptions): Promise<Blob>
}

export interface AppBackend {
  auth: AuthBackend
  aiJobs: AiJobsBackend
  files: FilesBackend
}

export interface AppBackendConfig {
  authMode: BackendAdapterMode
  aiMode: BackendAdapterMode
  filesMode: BackendAdapterMode
  serviceEngineUrl: string
  modelEngineUrl: string
}
