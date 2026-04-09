import type { Module } from 'vuex'
import type { Page } from '@/types/page'
import type { FileAdapter, PageRecord } from '@/file-adapter'

interface PagesState {
  byProject: Record<string, Page[]>
  fileAdapter: FileAdapter | null
  thumbnailUrls: Record<string, string>  // pageId → Blob URL (메모리 관리용)
}

// PageRecord (DB) → Page (UI). thumbnail은 별도로 설정.
function toPage(record: PageRecord): Page {
  return { ...record }
}

// Page (UI) → PageRecord (DB). thumbnail, originalImage 제거.
function toRecord(page: Page): PageRecord {
  const { thumbnail: _, originalImage: _2, ...record } = page
  return record as PageRecord
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

      const records = await adapter.listPages(projectId)
      const pageList = records.map(toPage)

      // 썸네일 Blob URL 생성
      for (const page of pageList) {
        const thumbBlob = await adapter.getThumbnail(page.id)
        if (thumbBlob) {
          const url = URL.createObjectURL(thumbBlob)
          page.thumbnail = url
          commit('SET_THUMBNAIL_URL', { pageId: page.id, url })
        }
      }

      commit('SET_PAGES', { projectId, pages: pageList })
    },

    async addPage({ commit, state }, { page, imageBlob }: { page: Page; imageBlob?: Blob }) {
      const adapter = state.fileAdapter
      if (adapter) {
        await adapter.savePage(toRecord(page))
        if (imageBlob) {
          await adapter.saveOriginalImage(page.id, imageBlob)
        }
      }
      commit('ADD_PAGE', page)
    },

    async updatePage({ commit, state }, page: Page) {
      const adapter = state.fileAdapter
      if (adapter) {
        await adapter.savePage(toRecord(page))
      }
      commit('UPDATE_PAGE', page)
    },

    async removePage({ commit, state }, { projectId, pageId }: { projectId: string; pageId: string }) {
      const adapter = state.fileAdapter
      if (adapter) {
        await adapter.deletePage(pageId)
      }
      commit('REMOVE_PAGE', { projectId, pageId })
    },
  },
}

export default pages
