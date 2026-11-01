<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import Icon from '../components/Icon.vue'

const ROLES = { admin: '관리자', staff: '담당자' }

const router = useRouter()
const user = ref(null)
const meta = ref(null)
const summary = ref(null)

const roleLabel = computed(() => ROLES[user.value?.role])
const college = computed(() => meta.value?.departments.find((d) => d.name === user.value?.department)?.college)
const stats = computed(() => [
  { label: '구독 게시판', value: summary.value?.subscriptions, to: '/boards' },
  { label: '다가오는 일정', value: summary.value?.upcoming, to: '/schedule' },
  { label: '내 신청서', value: summary.value?.applications, to: '/me/applications' },
])

onMounted(async () => {
  ;[user.value, meta.value, summary.value] = await Promise.all([api.me(), api.meta(), api.summary()])
})

async function logout() {
  await api.logout()
  router.push('/start')
}
</script>

<template>
  <header class="me-head"><h1 class="title-md">내 정보</h1></header>
  <main v-if="user" class="me-main">
    <section class="profile" aria-label="내 프로필">
      <div class="profile-top">
        <Icon name="user" :size="26" :width="1.8" />
        <span class="profile-name">
          {{ user.name }}
          <span v-if="roleLabel" class="role" :class="`role-${user.role}`"><Icon name="shield" :size="12" :width="2.4" />{{ roleLabel }}</span>
        </span>
        <RouterLink to="/me/profile" class="profile-edit"><Icon name="settings" :size="15" />프로필 수정</RouterLink>
      </div>
      <div class="profile-bottom">
        <span>{{ college ? `(${college}) ` : '' }}{{ user.department }}</span>
        <span>{{ user.grade }}학년</span>
      </div>
    </section>

    <section class="stats" aria-label="내 활동 요약">
      <RouterLink v-for="item in stats" :key="item.label" :to="item.to" class="stat">
        <b>{{ item.value ?? '-' }}</b><span>{{ item.label }}</span>
      </RouterLink>
    </section>

    <nav v-if="user.is_admin" class="menu" aria-label="행정실">
      <span class="menu-title">행정실</span>
      <RouterLink to="/admin" class="menu-row"><Icon name="edit" /><span>공지 작성·게시 관리</span><Icon name="next" :size="16" /></RouterLink>
    </nav>

    <nav class="menu" aria-label="내 활동">
      <span class="menu-title">내 활동</span>
      <RouterLink to="/me/applications" class="menu-row"><Icon name="doc" /><span>내 신청서</span><Icon name="next" :size="16" /></RouterLink>
      <RouterLink to="/schedule" class="menu-row"><Icon name="calendar" /><span>내 일정</span><Icon name="next" :size="16" /></RouterLink>
      <RouterLink to="/alerts" class="menu-row"><Icon name="bell" /><span>알림함</span><span v-if="summary?.unread_alerts" class="menu-count">{{ summary.unread_alerts }}</span><Icon name="next" :size="16" /></RouterLink>
      <RouterLink to="/boards" class="menu-row"><Icon name="grid" /><span>구독 게시판</span><Icon name="next" :size="16" /></RouterLink>
      <a :href="api.icsUrl()" class="menu-row"><Icon name="download" /><span>캘린더 파일 받기</span><Icon name="next" :size="16" /></a>
    </nav>

    <nav class="menu" aria-label="설정">
      <span class="menu-title">설정</span>
      <RouterLink to="/me/account" class="menu-row"><Icon name="lock" /><span>계정 관리</span><Icon name="next" :size="16" /></RouterLink>
      <RouterLink to="/privacy" class="menu-row"><Icon name="info" /><span>개인정보 처리 안내</span><Icon name="next" :size="16" /></RouterLink>
      <button class="menu-row" @click="logout"><Icon name="logout" /><span>로그아웃</span></button>
    </nav>

    <p v-if="meta" class="me-foot small">{{ meta.analyzer !== 'rules' ? `AI 분석 사용 중 · ${meta.model}` : '규칙 기반 분석 사용 중' }}</p>
  </main>
</template>
