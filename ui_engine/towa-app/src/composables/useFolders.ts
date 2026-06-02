import { computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useFileAdapter } from './useFileAdapter'
import { queryKeys } from './queryKeys'
import type { FileAdapter, FolderRecord } from '@/file-adapter'
import type { DeleteFolderMode } from '@/file-adapter/contracts'
import type { Folder, FolderNode } from '@/types/folder'
import { MAX_FOLDER_DEPTH } from '@/types/folder'

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

function buildTree(folders: Folder[]): FolderNode[] {
  const byParent = new Map<string | null, Folder[]>()
  for (const f of folders) {
    const arr = byParent.get(f.parentId) ?? []
    arr.push(f)
    byParent.set(f.parentId, arr)
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

function descendantIdsOf(folders: Folder[], folderId: string): string[] {
  const out: string[] = []
  const visit = (parent: string) => {
    for (const f of folders) {
      if (f.parentId === parent) {
        out.push(f.id)
        visit(f.id)
      }
    }
  }
  visit(folderId)
  return out
}

export function useFolders() {
  const fileAdapter = useFileAdapter()
  const qc = useQueryClient()

  const query = useQuery({
    queryKey: queryKeys.folders.all(),
    queryFn: () => fileAdapter.listFolders(),
  })

  const all = computed<Folder[]>(() => (query.data.value ?? []).map(toFolder))
  const tree = computed<FolderNode[]>(() => buildTree(all.value))

  function byId(id: string): Folder | undefined {
    return all.value.find((f) => f.id === id)
  }

  function childrenOf(parentId: string | null): Folder[] {
    return all.value
      .filter((f) => f.parentId === parentId)
      .sort((a, b) => a.name.localeCompare(b.name))
  }

  function wouldExceedMaxDepth(parentId: string | null): boolean {
    return depthOf(all.value, parentId) + 1 > MAX_FOLDER_DEPTH
  }

  function pathOf(folderId: string | null): string {
    if (!folderId) return ''
    const byIdMap = new Map(all.value.map((f) => [f.id, f]))
    const parts: string[] = []
    let cur: string | null = folderId
    while (cur != null) {
      const node = byIdMap.get(cur)
      if (!node) break
      parts.unshift(node.name)
      cur = node.parentId
    }
    return parts.join('/')
  }

  function descendantIds(folderId: string): string[] {
    return descendantIdsOf(all.value, folderId)
  }

  function invalidateFolders() {
    return qc.invalidateQueries({ queryKey: queryKeys.folders.all() })
  }
  function invalidateProjects() {
    return qc.invalidateQueries({ queryKey: queryKeys.projects.all() })
  }
  function invalidateTrash() {
    return qc.invalidateQueries({ queryKey: queryKeys.trash.all() })
  }

  const createMutation = useMutation({
    mutationFn: (input: { name: string; parentId: string | null }) =>
      fileAdapter.createFolder(input).then(toFolder),
    onSuccess: () => invalidateFolders(),
  })

  const renameMutation = useMutation({
    mutationFn: (input: { id: string; name: string }) =>
      fileAdapter.updateFolder(input.id, { name: input.name }).then(toFolder),
    onSuccess: () => invalidateFolders(),
  })

  const moveMutation = useMutation({
    mutationFn: (input: { id: string; parentId: string | null }) =>
      fileAdapter.updateFolder(input.id, { parentId: input.parentId }).then(toFolder),
    onSuccess: () => invalidateFolders(),
  })

  // Delete: invalidate folders + projects + trash. cascade-trash sweeps
  // a subtree's projects into trash on the server side, so the
  // projects/folders lists both need refresh.
  const removeMutation = useMutation({
    mutationFn: async (input: { id: string; mode: DeleteFolderMode }) => {
      const adapter: FileAdapter = fileAdapter
      await adapter.deleteFolder(input.id, input.mode)
    },
    onSuccess: () =>
      Promise.all([invalidateFolders(), invalidateProjects(), invalidateTrash()]),
  })

  const restoreMutation = useMutation({
    mutationFn: (id: string) => fileAdapter.restoreFolder(id).then(toFolder),
    onSuccess: () => Promise.all([invalidateFolders(), invalidateTrash()]),
  })

  const permanentlyDeleteMutation = useMutation({
    mutationFn: (id: string) => fileAdapter.permanentlyDeleteFolder(id),
    onSuccess: () => invalidateTrash(),
  })

  return {
    all,
    tree,
    byId,
    childrenOf,
    wouldExceedMaxDepth,
    pathOf,
    descendantIds,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
    create: createMutation.mutateAsync,
    rename: renameMutation.mutateAsync,
    move: moveMutation.mutateAsync,
    remove: removeMutation.mutateAsync,
    restore: restoreMutation.mutateAsync,
    permanentlyDelete: permanentlyDeleteMutation.mutateAsync,
  }
}
