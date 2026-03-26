<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useStore } from 'vuex'

const route = useRoute()
const store = useStore()

const projectId = computed(() => route.params.id as string)

watch(projectId, (id) => {
  store.commit('editor/SET_CURRENT_PROJECT', id)
}, { immediate: true })

// Sync activeTab with route
watch(
  () => route.name,
  (name) => {
    if (name === 'project-home') store.commit('editor/SET_ACTIVE_TAB', 'home')
    else if (name === 'editor') {
      store.commit('editor/SET_ACTIVE_TAB', 'edit')
      store.commit('editor/SET_LAST_EDIT_MODE', 'edit')
    }
    else if (name === 'detail-editor') {
      store.commit('editor/SET_ACTIVE_TAB', 'detail')
      store.commit('editor/SET_LAST_EDIT_MODE', 'detail')
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="h-[calc(100vh-48px)]">
    <router-view v-slot="{ Component }">
      <keep-alive :include="['ProjectHomeTab', 'EditorTab']">
        <component :is="Component" />
      </keep-alive>
    </router-view>
  </div>
</template>
