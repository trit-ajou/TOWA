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
  if (mode === 'standalone') {
    throw new Error(
      'Standalone mode is not supported in the current build. ' +
      'LocalFileAdapter is retained only as a skeleton for the future LocalFileManager ' +
      '(planned alongside Electron wrapping). Use VITE_DEPLOYMENT_MODE=cloud. See issue #37.',
    )
  }
  return new CloudFileAdapter(ctx.backend, ctx.getSessionKey)
}

export type { FileAdapter, PageSummary, PageSnapshotMeta, PageSnapshot } from './contracts'
export type { ProjectRecord, PageRecord } from './db'
export { LocalFileAdapter } from './local'
export { CloudFileAdapter } from './cloud'
export type { SessionKeyProvider } from './cloud'
