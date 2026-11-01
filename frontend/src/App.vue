<script setup>
import { useRoute } from 'vue-router'
import Icon from './components/Icon.vue'

const route = useRoute()
const tabs = [
  { to: '/', label: '피드', icon: 'home' },
  { to: '/schedule', label: '일정', icon: 'calendar' },
  { to: '/boards', label: '사업단', icon: 'grid' },
  { to: '/me', label: '내 정보', icon: 'user' },
]
</script>

<template>
  <div class="app">
    <RouterView :key="route.fullPath" />
    <nav v-if="route.meta.nav" class="tabs" aria-label="주요 메뉴">
      <RouterLink v-for="tab in tabs" :key="tab.to" :to="tab.to" class="tab">
        <Icon :name="tab.icon" :size="22" />{{ tab.label }}
      </RouterLink>
    </nav>
  </div>
</template>
