import type { Module } from 'vuex'
import type { FileAdapter, FolderRecord } from '@/file-adapter'
import type { Folder, FolderNode } from '@/types/folder'
import { MAX_FOLDER_DEPTH } from '@/types/folder'
import type { DeleteFolderMode } from '@/file-adapter/contracts'

interface FoldersState {
  list: Folder[]
  fileAdapter: FileAdapter | null
}

function toFolder(record: FolderRecord): Folder {
  return {
    id: record.id,
    name: record.name,
    parentId: record.parentId,
    userId: '',
    createdAt: record.createdAt,
    updatedAt: record.updatedAt,
    deletedAt: record.deletedAt,
  }
}

/** Build a tree (sorted by name) from a flat folder list. */
function buildTree(folders: Folder[]): FolderNode[] {
  const byParent = new Map<string | null, Folder[]>()
  for (const f of folders) {
    const key = f.parentId
    const arr = byParent.get(key) ?? []
    arr.push(f)
    byParent.set(key, arr)
  }
  for (const arr of byParent.values()) {
    arr.sort((a, b) => a.name.localeCompare(b.name))
  }
  const visit = (parentId: string | null): FolderNode[] =>
    (byParent.get(parentId) ?? []).map((f) => ({
      id: f.id,
      name: f.name,
      parentId: f.parentId,
      children: visit(f.id),
    }))
  return visit(null)
}

/** Depth of a folder (root = 0, top-level = 1). */
function depthOf(folders: Folder[], folderId: string | null): number {
  let depth = 0
  let cur = folderId
  const byId = new Map(folders.map((f) => [f.id, f]))
  while (cur != null) {
    depth += 1
    const node = byId.get(cur)
    if (!node) break
    cur = node.parentId
  }
  return depth
}

const folders: Module<FoldersState, unknown> = {
  namespaced: true,

  state: (): FoldersState => ({
    list: [],
    fileAdapter: null,
  }),

  getters: {
    all: (state) => state.list,
    byId: (state) => (id: string) => state.list.find((f) => f.id === id),
    tree: (state) => buildTree(state.list),
    childrenOf: (state) => (parentId: string | null) =>
      state.list.filter((f) => f.parentId === parentId).sort((a, b) => a.name.localeCompare(b.name)),
    /** True if adding a child to `parentId` would exceed MAX_FOLDER_DEPTH. */
    wouldExceedMaxDepth: (state) => (parentId: string | null) =>
      depthOf(state.list, parentId) + 1 > MAX_FOLDER_DEPTH,
    /** Path of names from root to folderId, joined by '/' for display. */
    pathOf: (state) => (folderId: string | null): string => {
      if (!folderId) return ''
      const byId = new Map(state.list.map((f) => [f.id, f]))
      const parts: string[] = []
      let cur: string | null = folderId
      while (cur != null) {
        const node = byId.get(cur)
        if (!node) break
        parts.unshift(node.name)
        cur = node.parentId
      }
      return parts.join('/')
    },
    /** ids of folderId and all descendants. */
    descendantIds: (state) => (folderId: string): string[] => {
      const out: string[] = []
      const visit = (parent: string) => {
        for (const f of state.list) {
          if (f.parentId === parent) {
            out.push(f.id)
            visit(f.id)
          }
        }
      }
      visit(folderId)
      return out
    },
  },

  mutations: {
    SET_FILE_ADAPTER(state, adapter: FileAdapter) {
      state.fileAdapter = adapter
    },
    SET_FOLDERS(state, list: Folder[]) {
      state.list = list
    },
    ADD_FOLDER(state, folder: Folder) {
      state.list.push(folder)
    },
    UPDATE_FOLDER(state, updated: Folder) {
      const idx = state.list.findIndex((f) => f.id === updated.id)
      if (idx !== -1) state.list[idx] = updated
    },
    REMOVE_FOLDERS(state, ids: string[]) {
      const set = new Set(ids)
      state.list = state.list.filter((f) => !set.has(f.id))
    },
  },

  actions: {
    async init({ commit }, adapter: FileAdapter) {
      commit('SET_FILE_ADAPTER', adapter)
    },

    async loadAll({ commit, state }) {
      const adapter = state.fileAdapter
      if (!adapter) return
      const records = await adapter.listFolders()
      commit('SET_FOLDERS', records.map(toFolder))
    },

    async create({ commit, state }, input: { name: string; parentId: string | null }) {
      const adapter = state.fileAdapter
      if (!adapter) throw new Error('FileAdapter not initialized')
      const record = await adapter.createFolder(input)
      const folder = toFolder(record)
      commit('ADD_FOLDER', folder)
      return folder
    },

    async rename({ commit, state }, input: { id: string; name: string }) {
      const adapter = state.fileAdapter
      if (!adapter) throw new Error('FileAdapter not initialized')
      const record = await adapter.updateFolder(input.id, { name: input.name })
      const folder = toFolder(record)
      commit('UPDATE_FOLDER', folder)
      return folder
    },

    async move({ commit, state }, input: { id: string; parentId: string | null }) {
      const adapter = state.fileAdapter
      if (!adapter) throw new Error('FileAdapter not initialized')
      const record = await adapter.updateFolder(input.id, { parentId: input.parentId })
      const folder = toFolder(record)
      commit('UPDATE_FOLDER', folder)
      return folder
    },

    /**
     * Delete a folder.
     * - 'empty': removed iff no children (server enforces).
     * - 'cascade-trash': self + all descendants + their projects → trash.
     * - 'reparent': children move to self's parent, self alone → trash.
     */
    async remove({ commit, dispatch, getters, state }, input: { id: string; mode: DeleteFolderMode }) {
      const adapter = state.fileAdapter
      if (!adapter) throw new Error('FileAdapter not initialized')
      await adapter.deleteFolder(input.id, input.mode)

      if (input.mode === 'cascade-trash') {
        const ids = [input.id, ...(getters.descendantIds(input.id) as string[])]
        commit('REMOVE_FOLDERS', ids)
        // 프로젝트 목록도 다시 받기 (cascade로 trash된 프로젝트가 active list에서 빠짐)
        await dispatch('projects/loadAll', undefined, { root: true })
      } else if (input.mode === 'reparent') {
        const self = getters.byId(input.id) as Folder | undefined
        const parentId = self?.parentId ?? null
        // 자식 폴더들의 parentId 갱신
        for (const f of state.list) {
          if (f.parentId === input.id) {
            commit('UPDATE_FOLDER', { ...f, parentId })
          }
        }
        commit('REMOVE_FOLDERS', [input.id])
      } else {
        commit('REMOVE_FOLDERS', [input.id])
      }
    },

    async restore({ commit, state }, id: string) {
      const adapter = state.fileAdapter
      if (!adapter) throw new Error('FileAdapter not initialized')
      const record = await adapter.restoreFolder(id)
      commit('ADD_FOLDER', toFolder(record))
    },

    async permanentlyDelete({ state }, id: string) {
      const adapter = state.fileAdapter
      if (!adapter) throw new Error('FileAdapter not initialized')
      await adapter.permanentlyDeleteFolder(id)
    },
  },
}

export default folders
