import { computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useFileAdapter } from './useFileAdapter'
import { queryKeys } from './queryKeys'
import type { TrashEntry } from '@/file-adapter/contracts'

export function useTrash() {
  const fileAdapter = useFileAdapter()
  const qc = useQueryClient()

  const query = useQuery({
    queryKey: queryKeys.trash.all(),
    queryFn: () => fileAdapter.listTrash(),
  })

  const all = computed<TrashEntry[]>(() => query.data.value ?? [])
  const folders = computed(() => all.value.filter((e): e is Extract<TrashEntry, { type: 'folder' }> => e.type === 'folder'))
  const projects = computed(() => all.value.filter((e): e is Extract<TrashEntry, { type: 'project' }> => e.type === 'project'))
  const isLoading = query.isLoading

  function invalidateAll() {
    return Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.trash.all() }),
      qc.invalidateQueries({ queryKey: queryKeys.folders.all() }),
      qc.invalidateQueries({ queryKey: queryKeys.projects.all() }),
    ])
  }

  const restoreFolderMutation = useMutation({
    mutationFn: (id: string) => fileAdapter.restoreFolder(id),
    onSuccess: () => invalidateAll(),
  })

  const restoreProjectMutation = useMutation({
    mutationFn: (id: string) => fileAdapter.restoreProject(id),
    onSuccess: () => invalidateAll(),
  })

  const permanentlyDeleteFolderMutation = useMutation({
    mutationFn: (id: string) => fileAdapter.permanentlyDeleteFolder(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.trash.all() }),
  })

  const permanentlyDeleteProjectMutation = useMutation({
    mutationFn: (id: string) => fileAdapter.permanentlyDeleteProject(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.trash.all() }),
  })

  return {
    all,
    folders,
    projects,
    isLoading,
    refetch: query.refetch,
    restoreFolder: restoreFolderMutation.mutateAsync,
    restoreProject: restoreProjectMutation.mutateAsync,
    permanentlyDeleteFolder: permanentlyDeleteFolderMutation.mutateAsync,
    permanentlyDeleteProject: permanentlyDeleteProjectMutation.mutateAsync,
  }
}
