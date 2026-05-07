import type { AppBackend } from '@/backend/contracts'
import type { DeploymentMode } from '@/config/deployment'

import type { FileAdapter } from './contracts'
import { CloudFileAdapter, type SessionKeyProvider } from './cloud'
import { LocalFileAdapter } from './local'

export interface FileAdapterContext {
  backend: AppBackend
  getSessionKey: SessionKeyProvider
}

export function createFileAdapter(
  mode: DeploymentMode,
  ctx: FileAdapterContext,
): FileAdapter {
  return mode === 'cloud'
    ? new CloudFileAdapter(ctx.backend, ctx.getSessionKey)
    : new LocalFileAdapter()
}

export type { FileAdapter, PageSummary, PageSnapshotMeta, PageSnapshot } from './contracts'
export type { ProjectRecord, PageRecord } from './db'
export { LocalFileAdapter } from './local'
export { CloudFileAdapter } from './cloud'
export type { SessionKeyProvider } from './cloud'
