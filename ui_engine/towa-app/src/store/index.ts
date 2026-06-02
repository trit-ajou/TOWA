import { createStore } from 'vuex'
import editor from './modules/editor'
import library from './modules/library'
import auth from './modules/auth'
// @ts-expect-error bitmappery store config (JS module)
import bmpStoreConfig from '@bitmappery/store'

// projects/folders/pages/trash modules were removed in #39; their
// surface is now provided by TanStack Query composables.
export default createStore({
  modules: {
    editor,
    library,
    auth,
    bmp: bmpStoreConfig,
  },
})
