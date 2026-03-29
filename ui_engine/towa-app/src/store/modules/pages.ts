import type { Module } from 'vuex'
import type { Page } from '@/types/page'
import { dummyPages } from '@/data/dummy'

interface PagesState {
  byProject: Record<string, Page[]>
}

const pages: Module<PagesState, unknown> = {
  namespaced: true,

  state: (): PagesState => ({
    byProject: dummyPages,
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
    SET_PAGES(state, { projectId, pages: pageList }: { projectId: string; pages: Page[] }) {
      state.byProject[projectId] = pageList
    },
    UPDATE_PAGE(state, page: Page) {
      const list = state.byProject[page.projectId]
      if (!list) return
      const idx = list.findIndex((p) => p.id === page.id)
      if (idx !== -1) list[idx] = page
    },
  },
}

export default pages
