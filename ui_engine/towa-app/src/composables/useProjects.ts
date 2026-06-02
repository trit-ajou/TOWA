import { computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useFileAdapter } from './useFileAdapter'
import { queryKeys } from './queryKeys'
import type { Project } from '@/types/project'
import type { ProjectRecord } from '@/file-adapter'

function toProject(record: ProjectRecord): Project {
  return { ...record }
}

function toRecord(project: Project): ProjectRecord {
  const { thumbnail: _drop, ...rest } = project
  return rest as ProjectRecord
}

/**
 * Reactive projects (TanStack Query). Replaces the legacy Vuex `projects`
 * module. Read surface mirrors prior getters (`all`, `byId`, `byFolder`,
 * `recentlyEdited`); writes are mutations that auto-invalidate the list.
 */
export function useProjects() {
  const fileAdapter = useFileAdapter()
  const qc = useQueryClient()

  const query = useQuery({
    queryKey: queryKeys.projects.all(),
    queryFn: () => fileAdapter.listProjects(),
  })

  const all = computed<Project[]>(() => (query.data.value ?? []).map(toProject))

  function byId(id: string): Project | undefined {
    return all.value.find((p) => p.id === id)
  }

  function byFolder(folderId: string | null): Project[] {
    return all.value.filter((p) => (p.folderId ?? null) === folderId)
  }

  function recentlyEdited(count: number = 3): Project[] {
    return [...all.value]
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
      .slice(0, count)
  }

  function invalidateProjects() {
    return qc.invalidateQueries({ queryKey: queryKeys.projects.all() })
  }
  function invalidateTrash() {
    return qc.invalidateQueries({ queryKey: queryKeys.trash.all() })
  }

  const createMutation = useMutation({
    mutationFn: (project: Project) => fileAdapter.createProject(toRecord(project)),
    onSuccess: () => invalidateProjects(),
  })

  const updateMutation = useMutation({
    mutationFn: (project: Project) =>
      fileAdapter.updateProject(project.id, toRecord(project)),
    onSuccess: () => invalidateProjects(),
  })

  const removeMutation = useMutation({
    mutationFn: (id: string) => fileAdapter.deleteProject(id),
    onSuccess: () => Promise.all([invalidateProjects(), invalidateTrash()]),
  })

  const restoreMutation = useMutation({
    mutationFn: (id: string) => fileAdapter.restoreProject(id),
    onSuccess: () => Promise.all([invalidateProjects(), invalidateTrash()]),
  })

  const permanentlyDeleteMutation = useMutation({
    mutationFn: (id: string) => fileAdapter.permanentlyDeleteProject(id),
    onSuccess: () => invalidateTrash(),
  })

  return {
    all,
    byId,
    byFolder,
    recentlyEdited,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
    create: createMutation.mutateAsync,
    update: updateMutation.mutateAsync,
    remove: removeMutation.mutateAsync,
    restore: restoreMutation.mutateAsync,
    permanentlyDelete: permanentlyDeleteMutation.mutateAsync,
  }
}
