/** Folder entity (mirrors service_engine spec, see issue #33). */
export interface Folder {
  id: string
  name: string
  parentId: string | null
  userId: string
  createdAt: string
  updatedAt: string
  deletedAt: string | null
}

/** Tree node built on the client from a flat Folder list. */
export interface FolderNode {
  id: string
  name: string
  parentId: string | null
  children: FolderNode[]
}

/** Max tree depth enforced in UI (backend is unrestricted). */
export const MAX_FOLDER_DEPTH = 5

/** Folder name validation (matches backend contract). */
export const FOLDER_NAME_MAX_LENGTH = 100
// eslint-disable-next-line no-control-regex
export const FOLDER_NAME_FORBIDDEN_CHARS = /[/\\\x00-\x1F\x7F]/

export type FolderNameError = 'empty' | 'too-long' | 'forbidden-char' | 'duplicate'

export function validateFolderNameSyntax(name: string): FolderNameError | null {
  const trimmed = name.trim()
  if (trimmed.length === 0) return 'empty'
  if (trimmed.length > FOLDER_NAME_MAX_LENGTH) return 'too-long'
  if (FOLDER_NAME_FORBIDDEN_CHARS.test(trimmed)) return 'forbidden-char'
  return null
}
