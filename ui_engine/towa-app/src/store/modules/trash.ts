import type { Module } from 'vuex'
import type { FileAdapter, TrashEntry } from '@/file-adapter/contracts'

interface TrashState {
  items: TrashEntry[]
  fileAdapter: FileAdapter | null
  loading: boolean
}

const trash: Module<TrashState, unknown> = {
  namespaced: true,

  state: (): TrashState => ({
    items: [],
    fileAdapter: null,
    loading: false,
  }),

  getters: {
    all: (state) => state.items,
    folders: (state) => state.items.filter((e): e is Extract<TrashEntry, { type: 'folder' }> => e.type === 'folder'),
    projects: (state) => state.items.filter((e): e is Extract<TrashEntry, { type: 'project' }> => e.type === 'project'),
    isLoading: (state) => state.loading,
  },

  mutations: {
    SET_FILE_ADAPTER(state, adapter: FileAdapter) {
      state.fileAdapter = adapter
    },
    SET_ITEMS(state, items: TrashEntry[]) {
      state.items = items
    },
    REMOVE_ITEM(state, payload: { type: 'folder' | 'project'; id: string }) {
      state.items = state.items.filter((e) => !(e.type === payload.type && e.item.id === payload.id))
    },
    SET_LOADING(state, v: boolean) {
      state.loading = v
    },
  },

  actions: {
    async init({ commit }, adapter: FileAdapter) {
      commit('SET_FILE_ADAPTER', adapter)
    },

    async loadAll({ commit, state }) {
      const adapter = state.fileAdapter
      if (!adapter) return
      commit('SET_LOADING', true)
      try {
        const items = await adapter.listTrash()
        commit('SET_ITEMS', items)
      } finally {
        commit('SET_LOADING', false)
      }
    },

    async restoreFolder({ commit, dispatch }, id: string) {
      await dispatch('folders/restore', id, { root: true })
      commit('REMOVE_ITEM', { type: 'folder', id })
    },

    async restoreProject({ commit, dispatch }, id: string) {
      await dispatch('projects/restore', id, { root: true })
      commit('REMOVE_ITEM', { type: 'project', id })
    },

    async permanentlyDeleteFolder({ commit, dispatch }, id: string) {
      await dispatch('folders/permanentlyDelete', id, { root: true })
      commit('REMOVE_ITEM', { type: 'folder', id })
    },

    async permanentlyDeleteProject({ commit, dispatch }, id: string) {
      await dispatch('projects/permanentlyDelete', id, { root: true })
      commit('REMOVE_ITEM', { type: 'project', id })
    },
  },
}

export default trash
