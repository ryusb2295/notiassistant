<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import NoticeCard from '../components/NoticeCard.vue'

const user = ref(null)
const feed = ref(null)
const sources = ref([])
const alerts = ref([])
const showOthers = ref(false)
const error = ref('')

const unread = computed(() => alerts.value.filter((alert) => !alert.read).length)
const subscribed = computed(() => sources.value.filter((s) => s.subscribed))

onMounted(async () => {
  try {
    ;[user.value, feed.value, sources.value, alerts.value] = await Promise.all([
      api.user(), api.feed(), api.sources(), api.alerts(),
    ])
  } catch (failure) {
    error.value = failure.message
  }
})
</script>

<template>
  <header class="head">
    <div class="head-row">
      <span class="brand"><span class="brand-mark"><Icon name="logo" :size="16" :width="2.2" style="color: #fff" /></span>공지비서</span>
      <RouterLink to="/alerts" class="icon-btn" :aria-label="`알림함, 읽지 않은 알림 ${unread}개`">
        <Icon name="bell" :size="22" :width="1.8" /><span v-if="unread" class="dot"></span>
      </RouterLink>
    </div>
    <div v-if="feed && user">
      <p class="muted">{{ user.name }}님, 최근 7일 새 공지 {{ feed.new_count }}개를 읽었어요</p>
      <h1 class="title-lg">해당되는 공지는 <span class="accent">{{ feed.match_count }}개</span>예요</h1>
    </div>
    <div class="chips">
      <span v-for="source in subscribed" :key="source.id" class="chip">{{ source.name }}</span>
      <RouterLink to="/boards" class="chip chip-add">+ 게시판 추가</RouterLink>
    </div>
  </header>
  <main class="main">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <template v-if="feed">
      <template v-if="feed.urgent.length">
        <span class="section-label">마감 임박</span>
        <NoticeCard v-for="notice in feed.urgent" :key="notice.id" :notice="notice" variant="urgent" />
      </template>
      <template v-if="feed.mine.length">
        <span class="section-label">나에게 해당</span>
        <NoticeCard v-for="notice in feed.mine" :key="notice.id" :notice="notice" variant="mine" />
      </template>
      <p v-if="!feed.match_count" class="empty">지금 해당되는 공지가 없어요</p>
      <div v-if="feed.others.length" class="toggle-row">
        <span class="section-label">그 외 대상 제한 없는 공지 {{ feed.others.length }}개</span>
        <button class="link-btn" :aria-expanded="showOthers" @click="showOthers = !showOthers">{{ showOthers ? '접기' : '펼치기' }}</button>
      </div>
      <template v-if="showOthers">
        <NoticeCard v-for="notice in feed.others" :key="notice.id" :notice="notice" />
      </template>
      <p v-if="feed.hidden_count" class="small" style="padding: 0 4px">대상이 아닌 공지 {{ feed.hidden_count }}개는 숨겼어요</p>
    </template>
  </main>
</template>
