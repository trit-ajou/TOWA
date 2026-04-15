import { createStore } from 'vuex'
import projects from './modules/projects'
import pages from './modules/pages'
import editor from './modules/editor'
import library from './modules/library'
// @ts-expect-error bitmappery store config (JS module)
import bmpStoreConfig from '@bitmappery/store'

export default createStore({
  modules: {
    projects,
    pages,
    editor,
    library,
    bmp: bmpStoreConfig,
  },
})
