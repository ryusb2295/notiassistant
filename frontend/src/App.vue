<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, isLoggedIn } from './api'
import Icon from './components/Icon.vue'

const route = useRoute()
const router = useRouter()
const unread = ref(0)
const tabs = [
  { to: '/', label: '피드', icon: 'home' },
  { to: '/schedule', label: '일정', icon: 'calendar' },
  { to: '/alerts', label: '알림', icon: 'bell', badge: true },
  { to: '/boards', label: '게시판', icon: 'grid' },
  { to: '/me', label: '내 정보', icon: 'user' },
]

// 화면 이동이 끝날 때마다(첫 화면 포함) 읽지 않은 알림 수를 갱신해 탭에 표시한다.
router.afterEach(async (to) => {
  if (!to.meta.nav || !isLoggedIn()) return
  try {
    unread.value = (await api.summary()).unread_alerts
  } catch {
    unread.value = 0
  }
})
</script>

<template>
  <div class="app">
    <RouterView :key="route.fullPath" />
    <nav v-if="route.meta.nav" class="tabs" aria-label="주요 메뉴">
      <RouterLink v-for="tab in tabs" :key="tab.to" :to="tab.to" class="tab">
        <span class="tab-icon">
          <Icon :name="tab.icon" :size="22" />
          <span v-if="tab.badge && unread" class="tab-badge" :aria-label="`읽지 않은 알림 ${unread}개`">{{ unread > 99 ? '99+' : unread }}</span>
        </span>
        {{ tab.label }}
      </RouterLink>
    </nav>
  </div>
</template>
