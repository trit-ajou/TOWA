import type { Module } from 'vuex'
import type { Page } from '@/types/page'
import type { FileAdapter, PageSnapshot } from '@/file-adapter'

interface PagesState {
  byProject: Record<string, Page[]>
  fileAdapter: FileAdapter | null
  thumbnailUrls: Record<string, string>  // pageId → Blob URL (메모리 관리용)
}

const pages: Module<PagesState, unknown> = {
  namespaced: true,

  state: (): PagesState => ({
    byProject: {},
    fileAdapter: null,
    thumbnailUrls: {},
  }),

  getters: {
    forProject: (state) => (projectId: string): Page[] => {
      return state.byProject[projectId] ?? []
    },
    byId: (state) => (projectId: string, pageId: string): Page | undefined => {
      return state.byProject[projectId]?.find((p) => p.id === pageId)
    },
  },

  mutations: {
    SET_FILE_ADAPTER(state, adapter: FileAdapter) {
      state.fileAdapter = adapter
    },
    SET_PAGES(state, { projectId, pages: pageList }: { projectId: string; pages: Page[] }) {
      state.byProject[projectId] = pageList
    },
    ADD_PAGE(state, page: Page) {
      const list = state.byProject[page.projectId]
      if (list) {
        list.push(page)
      } else {
        state.byProject[page.projectId] = [page]
      }
    },
    UPDATE_PAGE(state, page: Page) {
      const list = state.byProject[page.projectId]
      if (!list) return
      const idx = list.findIndex((p) => p.id === page.id)
      if (idx !== -1) list[idx] = page
    },
    REMOVE_PAGE(state, { projectId, pageId }: { projectId: string; pageId: string }) {
      const list = state.byProject[projectId]
      if (!list) return
      state.byProject[projectId] = list.filter((p) => p.id !== pageId)
      // Blob URL 해제
      const url = state.thumbnailUrls[pageId]
      if (url) {
        URL.revokeObjectURL(url)
        delete state.thumbnailUrls[pageId]
      }
    },
    /** deletePage 후 dense reindex 반영용 */
    REINDEX_PAGES(state, projectId: string) {
      const list = state.byProject[projectId]
      if (!list) return
      list.sort((a, b) => a.index - b.index)
      list.forEach((p, i) => { p.index = i + 1 })
    },
    SET_THUMBNAIL_URL(state, { pageId, url }: { pageId: string; url: string }) {
      // 기존 Blob URL이 있으면 해제
      const old = state.thumbnailUrls[pageId]
      if (old) URL.revokeObjectURL(old)
      state.thumbnailUrls[pageId] = url
    },
  },

  actions: {
    async init({ commit }, adapter: FileAdapter) {
      commit('SET_FILE_ADAPTER', adapter)
    },

    async loadForProject({ commit, state }, projectId: string) {
      const adapter = state.fileAdapter
      if (!adapter) return

      const summaries = await adapter.listPageSummaries(projectId)
      const pageList: Page[] = []

      for (const s of summaries) {
        const thumbBlob = await adapter.getThumbnailBlob(s.id)
        let thumbnail: string | undefined
        if (thumbBlob) {
          const url = URL.createObjectURL(thumbBlob)
          thumbnail = url
          commit('SET_THUMBNAIL_URL', { pageId: s.id, url })
        }

        pageList.push({
          id: s.id,
          projectId: s.projectId,
          index: s.index,
          status: s.status,
          thumbnail,
        })
      }

      commit('SET_PAGES', { projectId, pages: pageList })
    },

    async addPage({ commit, state }, { projectId, snapshot }: { projectId: string; snapshot: PageSnapshot }) {
      const adapter = state.fileAdapter
      if (!adapter) return

      const summary = await adapter.createPage(projectId, snapshot)

      // 썸네일 Blob URL 생성
      const thumbUrl = URL.createObjectURL(snapshot.thumbnail)
      commit('SET_THUMBNAIL_URL', { pageId: summary.id, url: thumbUrl })

      const page: Page = {
        id: summary.id,
        projectId: summary.projectId,
        index: summary.index,
        status: summary.status,
        thumbnail: thumbUrl,
      }
      commit('ADD_PAGE', page)
    },

    async updatePage({ commit, state }, page: Page) {
      // metadata만 업데이트 (snapshot 전체 저장이 아닌 경우)
      // 실제로는 savePageSnapshot을 usePageLoader에서 호출
      // 여기서는 Vuex state만 업데이트
      commit('UPDATE_PAGE', page)
    },

    async removePage({ commit, state }, { projectId, pageId }: { projectId: string; pageId: string }) {
      const adapter = state.fileAdapter
      if (adapter) {
        await adapter.deletePage(pageId)
      }
      commit('REMOVE_PAGE', { projectId, pageId })
      // dense reindex 반영
      commit('REINDEX_PAGES', projectId)
    },
  },
}

export default pages
