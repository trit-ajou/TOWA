import type { Module } from 'vuex'
import type { Project } from '@/types/project'
import { dummyProjects } from '@/data/dummy'

interface ProjectsState {
  list: Project[]
}

const projects: Module<ProjectsState, unknown> = {
  namespaced: true,

  state: (): ProjectsState => ({
    list: dummyProjects,
  }),

  getters: {
    all: (state) => state.list,
    byId: (state) => (id: string) => state.list.find((p) => p.id === id),

    // Filter by folder path prefix (e.g. '주간연재' matches '주간연재/점프')
    byFolder: (state) => (folderPath: string | null) => {
      if (!folderPath) return state.list
      return state.list.filter((p) => p.folder === folderPath || p.folder.startsWith(folderPath + '/'))
    },

    // Recently edited (sorted by updatedAt desc)
    recentlyEdited: (state) => (count: number = 3) => {
      return [...state.list]
        .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
        .slice(0, count)
    },
  },

  mutations: {
    ADD_PROJECT(state, project: Project) {
      state.list.unshift(project)
    },
    UPDATE_PROJECT(state, updated: Project) {
      const idx = state.list.findIndex((p) => p.id === updated.id)
      if (idx !== -1) state.list[idx] = updated
    },
    REMOVE_PROJECT(state, id: string) {
      state.list = state.list.filter((p) => p.id !== id)
    },
  },

  actions: {
    create({ commit }, project: Project) {
      commit('ADD_PROJECT', project)
    },
  },
}

export default projects
