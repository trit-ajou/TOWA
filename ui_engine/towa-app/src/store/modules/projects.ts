import type { Module } from 'vuex'
import type { Project } from '@/types/project'
import type { FileAdapter, ProjectRecord } from '@/file-adapter'

interface ProjectsState {
  list: Project[]
  fileAdapter: FileAdapter | null
}

// ProjectRecord (DB) → Project (UI) 변환. thumbnail은 런타임에 별도 설정.
function toProject(record: ProjectRecord): Project {
  return { ...record }
}

// Project (UI) → ProjectRecord (DB) 변환. thumbnail 제거.
function toRecord(project: Project): ProjectRecord {
  const { thumbnail: _, ...record } = project
  return record as ProjectRecord
}

const projects: Module<ProjectsState, unknown> = {
  namespaced: true,

  state: (): ProjectsState => ({
    list: [],
    fileAdapter: null,
  }),

  getters: {
    all: (state) => state.list,
    byId: (state) => (id: string) => state.list.find((p) => p.id === id),

    byFolder: (state) => (folderPath: string | null) => {
      if (!folderPath) return state.list
      return state.list.filter((p) => p.folder === folderPath || p.folder.startsWith(folderPath + '/'))
    },

    recentlyEdited: (state) => (count: number = 3) => {
      return [...state.list]
        .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
        .slice(0, count)
    },
  },

  mutations: {
    SET_FILE_ADAPTER(state, adapter: FileAdapter) {
      state.fileAdapter = adapter
    },
    SET_PROJECTS(state, projects: Project[]) {
      state.list = projects
    },
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
    async init({ commit }, adapter: FileAdapter) {
      commit('SET_FILE_ADAPTER', adapter)
    },

    async loadAll({ commit, state }) {
      const adapter = state.fileAdapter
      if (!adapter) return
      const records = await adapter.listProjects()
      commit('SET_PROJECTS', records.map(toProject))
    },

    async create({ commit, state }, project: Project) {
      const adapter = state.fileAdapter
      if (adapter) {
        await adapter.createProject(toRecord(project))
      }
      commit('ADD_PROJECT', project)
    },

    async update({ commit, state }, project: Project) {
      const adapter = state.fileAdapter
      if (adapter) {
        await adapter.updateProject(project.id, toRecord(project))
      }
      commit('UPDATE_PROJECT', project)
    },

    async remove({ commit, state }, id: string) {
      const adapter = state.fileAdapter
      if (adapter) {
        await adapter.deleteProject(id)
      }
      commit('REMOVE_PROJECT', id)
    },
  },
}

export default projects
