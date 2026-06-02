import { computed, toRef, unref, type MaybeRef } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { useFileAdapter } from './useFileAdapter'
import { queryKeys } from './queryKeys'
import type { Page } from '@/types/page'
import type { PageSnapshot, PageSummary } from '@/file-adapter'

function toPage(s: PageSummary): Page {
  // Object URL is intentionally not produced here; thumbnail URLs are owned
  // by individual components via the dedicated useThumbnailUrl composable
  // (introduced in Phase 3 of #39). This keeps revokeObjectURL local to
  // component lifecycles.
  return {
    id: s.id,
    projectId: s.projectId,
    index: s.index,
    status: s.status,
    thumbnail: undefined,
  }
}

/** Per-project page list (Vuex `pages` module replacement). */
export function usePages(projectId: MaybeRef<string>) {
  const fileAdapter = useFileAdapter()
  const qc = useQueryClient()
  const pidRef = toRef(projectId)

  const query = useQuery({
    queryKey: computed(() => queryKeys.pages.byProject(unref(pidRef))),
    queryFn: () => fileAdapter.listPageSummaries(unref(pidRef)),
    enabled: computed(() => Boolean(unref(pidRef))),
  })

  const list = computed<Page[]>(() => (query.data.value ?? []).map(toPage))

  function byId(pageId: string): Page | undefined {
    return list.value.find((p) => p.id === pageId)
  }

  function invalidatePages() {
    return qc.invalidateQueries({ queryKey: queryKeys.pages.byProject(unref(pidRef)) })
  }

  const addPageMutation = useMutation({
    mutationFn: (input: { projectId: string; snapshot: PageSnapshot }) =>
      fileAdapter.createPage(input.projectId, input.snapshot),
    onSuccess: (_data, vars) =>
      qc.invalidateQueries({ queryKey: queryKeys.pages.byProject(vars.projectId) }),
  })

  // updatePage was historically a Vuex-only mutation; server-side metadata
  // is overwritten via savePageSnapshot. We keep the surface for callers
  // but route through a refetch so the cache reflects whatever the server
  // last accepted.
  const updatePageMutation = useMutation({
    mutationFn: async (_page: Page) => {
      await invalidatePages()
    },
  })

  const removePageMutation = useMutation({
    mutationFn: (input: { projectId: string; pageId: string }) =>
      fileAdapter.deletePage(input.pageId),
    onSuccess: (_data, vars) =>
      qc.invalidateQueries({ queryKey: queryKeys.pages.byProject(vars.projectId) }),
  })

  return {
    list,
    byId,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
    addPage: addPageMutation.mutateAsync,
    updatePage: updatePageMutation.mutateAsync,
    removePage: removePageMutation.mutateAsync,
  }
}
