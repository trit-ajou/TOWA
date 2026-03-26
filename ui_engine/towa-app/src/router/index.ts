import { createRouter, createWebHistory } from 'vue-router'
import LibraryView from '@/views/LibraryView.vue'
import ProjectView from '@/views/ProjectView.vue'
import ProjectHomeTab from '@/views/ProjectHomeTab.vue'
import EditorTab from '@/views/EditorTab.vue'
import DetailEditorTab from '@/views/DetailEditorTab.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'library',
      component: LibraryView,
    },
    {
      path: '/project/:id',
      component: ProjectView,
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

export default router
