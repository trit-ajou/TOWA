import type { Module } from 'vuex'
import type { FolderNode } from '@/types/folder'
import type { ProjectStatus } from '@/types/project'

interface LibraryState {
  currentPath: string[]  // e.g. [] = root, ['주간연재'] = 주간연재 폴더, ['주간연재', '점프'] = 하위
  statusFilter: ProjectStatus | 'all'
  folderTree: FolderNode[]
}

const library: Module<LibraryState, unknown> = {
  namespaced: true,

  state: (): LibraryState => ({
    currentPath: [],
    statusFilter: 'all',
    folderTree: [
      {
        id: 'f-weekly',
        name: '주간연재',
        children: [
          { id: 'f-jump', name: '점프', children: [] },
          { id: 'f-magazine', name: '매거진', children: [] },
        ],
      },
      {
        id: 'f-webtoon',
        name: '웹툰',
        children: [
          { id: 'f-naver', name: '네이버', children: [] },
          { id: 'f-kakao', name: '카카오', children: [] },
        ],
      },
      {
        id: 'f-tankobon',
        name: '단행본',
        children: [],
      },
    ],
  }),

  getters: {
    currentPath: (state) => state.currentPath,
    currentFolderName: (state) => state.currentPath.length > 0 ? state.currentPath[state.currentPath.length - 1] : null,
    statusFilter: (state) => state.statusFilter,
    folderTree: (state) => state.folderTree,

    // Get subfolders at current path
    currentSubfolders: (state): FolderNode[] => {
      if (state.currentPath.length === 0) return state.folderTree
      let nodes = state.folderTree
      for (const segment of state.currentPath) {
        const found = nodes.find((n) => n.name === segment)
        if (!found) return []
        nodes = found.children
      }
      return nodes
    },

    // Build full folder path string for matching with project.folder
    currentFolderPath: (state): string | null => {
      return state.currentPath.length > 0 ? state.currentPath.join('/') : null
    },
  },

  mutations: {
    SET_PATH(state, path: string[]) {
      state.currentPath = path
    },
    NAVIGATE_INTO(state, folderName: string) {
      state.currentPath = [...state.currentPath, folderName]
    },
    NAVIGATE_UP(state) {
      state.currentPath = state.currentPath.slice(0, -1)
    },
    SET_STATUS_FILTER(state, filter: ProjectStatus | 'all') {
      state.statusFilter = filter
    },
  },
}

export default library
