import { createRouter, createWebHistory } from 'vue-router'
import LandingView from '@/views/LandingView.vue'
import LoginView from '@/views/LoginView.vue'
import LibraryView from '@/views/LibraryView.vue'
import ProjectView from '@/views/ProjectView.vue'
import ProjectHomeTab from '@/views/ProjectHomeTab.vue'
import EditorTab from '@/views/EditorTab.vue'
import DetailEditorTab from '@/views/DetailEditorTab.vue'
import store from '@/store'
import { DEPLOYMENT_MODE } from '@/config/deployment'
import KeyboardService from '@bitmappery/services/keyboard-service'

const CANVAS_ROUTES = new Set(['editor', 'detail-editor'])

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: LandingView,
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
    },
    {
      path: '/library',
      name: 'library',
      component: LibraryView,
      meta: { requiresAuth: true },
    },
    {
      path: '/project/:id',
      component: ProjectView,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'project-home',
          component: ProjectHomeTab,
        },
        {
          path: 'edit',
          name: 'editor',
          component: EditorTab,
        },
        {
          path: 'detail',
          name: 'detail-editor',
          component: DetailEditorTab,
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  KeyboardService.setSuspended(!CANVAS_ROUTES.has(to.name as string))

  const isCloud = DEPLOYMENT_MODE.value === 'cloud'
  const isLoggedIn = store.getters['auth/isLoggedIn']

  if (to.name === 'landing' && (!isCloud || isLoggedIn)) {
    return { name: 'library' }
  }

  if (isCloud && to.meta.requiresAuth && !isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
