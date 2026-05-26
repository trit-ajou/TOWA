import type { Module } from 'vuex'
import type { ProjectStatus } from '@/types/project'

interface LibraryState {
  /** null = 루트(전체). */
  currentFolderId: string | null
  statusFilter: ProjectStatus | 'all'
  searchQuery: string
}

const library: Module<LibraryState, unknown> = {
  namespaced: true,

  state: (): LibraryState => ({
    currentFolderId: null,
    statusFilter: 'all',
    searchQuery: '',
  }),

  getters: {
    currentFolderId: (state) => state.currentFolderId,
    statusFilter: (state) => state.statusFilter,
    searchQuery: (state) => state.searchQuery,
  },

  mutations: {
    SET_CURRENT_FOLDER(state, folderId: string | null) {
      state.currentFolderId = folderId
    },
    SET_STATUS_FILTER(state, filter: ProjectStatus | 'all') {
      state.statusFilter = filter
    },
    SET_SEARCH_QUERY(state, q: string) {
      state.searchQuery = q
    },
  },
}

export default library
