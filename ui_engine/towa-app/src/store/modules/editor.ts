import type { Module } from 'vuex'
import type { TextBlock } from '@/types/text-block'

export type ProjectTab = 'home' | 'edit' | 'detail'
export type ProjectHomeLayout = 'vertical' | 'horizontal'
export type EditMode = 'edit' | 'detail'

interface EditorState {
  currentProjectId: string | null
  currentPageId: string | null
  selectedPageId: string | null
  activeTab: ProjectTab
  projectHomeLayout: ProjectHomeLayout
  lastEditMode: EditMode
  pagePanelCollapsed: boolean
  canvasViewMode: 'single-split' | 'spread'
  theme: 'dark' | 'light'
  selectedTextBlockId: string | null
  layerVisibility: Record<string, boolean>
  zoomLevel: number
}

const editor: Module<EditorState, unknown> = {
  namespaced: true,

  state: (): EditorState => ({
    currentProjectId: null,
    currentPageId: null,
    selectedPageId: null,
    activeTab: 'home',
    projectHomeLayout: 'horizontal',
    lastEditMode: 'edit',
    pagePanelCollapsed: false,
    canvasViewMode: 'single-split',
    theme: 'dark',
    selectedTextBlockId: null,
    layerVisibility: {},
    zoomLevel: 100,
  }),

  getters: {
    currentProjectId: (state) => state.currentProjectId,
    currentPageId: (state) => state.currentPageId,
    selectedPageId: (state) => state.selectedPageId,
    activeTab: (state) => state.activeTab,
    projectHomeLayout: (state) => state.projectHomeLayout,
    lastEditMode: (state) => state.lastEditMode,
    pagePanelCollapsed: (state) => state.pagePanelCollapsed,
    canvasViewMode: (state) => state.canvasViewMode,
    theme: (state) => state.theme,
    selectedTextBlockId: (state) => state.selectedTextBlockId,
    isLayerVisible: (state) => (layerId: string) => state.layerVisibility[layerId] ?? true,
    zoomLevel: (state) => state.zoomLevel,
  },

  mutations: {
    SET_CURRENT_PROJECT(state, projectId: string | null) {
      state.currentProjectId = projectId
    },
    SET_CURRENT_PAGE(state, pageId: string | null) {
      state.currentPageId = pageId
    },
    SET_SELECTED_PAGE(state, pageId: string | null) {
      state.selectedPageId = pageId
    },
    SET_ACTIVE_TAB(state, tab: ProjectTab) {
      state.activeTab = tab
    },
    SET_PROJECT_HOME_LAYOUT(state, layout: ProjectHomeLayout) {
      state.projectHomeLayout = layout
    },
    SET_LAST_EDIT_MODE(state, mode: EditMode) {
      state.lastEditMode = mode
    },
    SET_PAGE_PANEL_COLLAPSED(state, collapsed: boolean) {
      state.pagePanelCollapsed = collapsed
    },
    SET_CANVAS_VIEW_MODE(state, mode: 'single-split' | 'spread') {
      state.canvasViewMode = mode
    },
    SET_THEME(state, theme: 'dark' | 'light') {
      state.theme = theme
      document.documentElement.className = theme
    },
    SELECT_TEXT_BLOCK(state, blockId: string | null) {
      state.selectedTextBlockId = blockId
    },
    TOGGLE_LAYER(state, layerId: string) {
      const current = state.layerVisibility[layerId] ?? true
      state.layerVisibility[layerId] = !current
    },
    SET_LAYER_VISIBILITY(state, { layerId, visible }: { layerId: string; visible: boolean }) {
      state.layerVisibility[layerId] = visible
    },
    SET_ZOOM(state, level: number) {
      state.zoomLevel = Math.max(25, Math.min(400, level))
    },
    UPDATE_TEXT_BLOCK_TRANSLATION(_state, _payload: { block: TextBlock; translation: string }) {
      // placeholder
    },
  },
}

export default editor
