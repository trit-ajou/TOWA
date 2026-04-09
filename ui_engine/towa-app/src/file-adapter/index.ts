import type { FileAdapter } from './contracts'
import { LocalFileAdapter } from './local'

export function createFileAdapter(): FileAdapter {
  // standalone 모드만 지원. cloud 모드 추가 시 여기서 분기.
  return new LocalFileAdapter()
}

export type { FileAdapter } from './contracts'
export type { ProjectRecord, PageRecord } from './db'
