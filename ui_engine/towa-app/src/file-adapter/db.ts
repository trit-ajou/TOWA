import { openDB, type IDBPDatabase, type DBSchema } from 'idb'
import type { ProjectStatus, ProjectConfig } from '@/types/project'
import type { PageStatus } from '@/types/page'
import type { TextBlock } from '@/types/text-block'

// --- DB record types (stored in IndexedDB, no Blob URLs or runtime-only fields) ---

export interface ProjectRecord {
  id: string
  name: string
  sourceLang: string
  targetLang: string
  pageCount: number
  status: ProjectStatus
  folder: string
  config: ProjectConfig
  createdAt: string
  updatedAt: string
  /** Project cover thumbnail URL (cloud only; local leaves undefined). */
  thumbnailUrl?: string | null
}

export interface PageRecord {
  id: string
  projectId: string
  index: number
  status: PageStatus
  textBlocks: TextBlock[]
}

// --- IndexedDB schema ---

interface TowaDBSchema extends DBSchema {
  'projects': {
    key: string
    value: ProjectRecord
    indexes: {
      'by-folder': string
      'by-updated': string
    }
  }
  'pages': {
    key: string
    value: PageRecord
    indexes: {
      'by-project': string
      'by-project-index': [string, number]
    }
  }
  'page-images': {
    key: string
    value: { pageId: string; blob: Blob }
  }
  'page-layers': {
    key: string
    value: { pageId: string; blob: Blob; savedAt: string }
  }
  'thumbnails': {
    key: string
    value: { pageId: string; blob: Blob }
  }
  'page-cache': {
    key: string
    value: { pageId: string; blob: Blob; accessedAt: number }
    indexes: { 'by-accessed': number }
  }
}

const DB_NAME = 'towa-db'
const DB_VERSION = 1

let dbPromise: Promise<IDBPDatabase<TowaDBSchema>> | null = null

export function getDB(): Promise<IDBPDatabase<TowaDBSchema>> {
  if (!dbPromise) {
    dbPromise = openDB<TowaDBSchema>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        // projects
        const projectStore = db.createObjectStore('projects', { keyPath: 'id' })
        projectStore.createIndex('by-folder', 'folder')
        projectStore.createIndex('by-updated', 'updatedAt')

        // pages
        const pageStore = db.createObjectStore('pages', { keyPath: 'id' })
        pageStore.createIndex('by-project', 'projectId')
        pageStore.createIndex('by-project-index', ['projectId', 'index'])

        // binary stores
        db.createObjectStore('page-images', { keyPath: 'pageId' })
        db.createObjectStore('page-layers', { keyPath: 'pageId' })
        db.createObjectStore('thumbnails', { keyPath: 'pageId' })

        // cache
        const cacheStore = db.createObjectStore('page-cache', { keyPath: 'pageId' })
        cacheStore.createIndex('by-accessed', 'accessedAt')
      },
    })
  }
  return dbPromise
}

export type { TowaDBSchema }
