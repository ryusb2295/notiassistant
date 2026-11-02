<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import PagedList from '../components/PagedList.vue'

const user = ref(null)
const feed = ref(null)
const sources = ref([])
const alerts = ref([])
const showOthers = ref(false)
const filter = ref(null)
const error = ref('')

const unread = computed(() => alerts.value.filter((alert) => !alert.read).length)
const subscribed = computed(() => sources.value.filter((s) => s.subscribed))
const filterName = computed(() => subscribed.value.find((s) => s.id === filter.value)?.name)

// 칩을 누르면 그 게시판 공지만, 다시 누르면 전체를 보여준다.
async function toggleFilter(id) {
  filter.value = filter.value === id ? null : id
  showOthers.value = Boolean(filter.value)
  try {
    feed.value = await api.feed(filter.value)
  } catch (failure) {
    error.value = failure.message
  }
}

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
      <button v-for="source in subscribed" :key="source.id" class="chip chip-filter" :aria-pressed="filter === source.id" @click="toggleFilter(source.id)">{{ source.name }}</button>
      <RouterLink to="/boards" class="chip chip-add">+ 게시판 추가</RouterLink>
    </div>
  </header>
  <main class="main">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div v-if="filter" class="filter-bar">
      <span><b>{{ filterName }}</b> 공지만 보는 중</span>
      <button class="link-btn" @click="toggleFilter(filter)">전체 보기</button>
    </div>
    <template v-if="feed">
      <template v-if="feed.urgent.length">
        <span class="section-label">마감 임박</span>
        <PagedList :notices="feed.urgent" variant="urgent" label="마감 임박" :size="4" />
      </template>
      <template v-if="feed.mine.length">
        <span class="section-label">나에게 해당</span>
        <PagedList :notices="feed.mine" variant="mine" label="나에게 해당" />
      </template>
      <p v-if="!feed.match_count" class="empty">지금 해당되는 공지가 없어요</p>
      <div v-if="feed.others.length" class="toggle-row">
        <span class="section-label">그 외 대상 제한 없는 공지 {{ feed.others.length }}개</span>
        <button class="link-btn" :aria-expanded="showOthers" @click="showOthers = !showOthers">{{ showOthers ? '접기' : '펼치기' }}</button>
      </div>
      <template v-if="showOthers">
        <PagedList :notices="feed.others" label="그 외 공지" />
      </template>
      <p v-if="feed.hidden_count" class="small" style="padding: 0 4px">대상이 아닌 공지 {{ feed.hidden_count }}개는 숨겼어요</p>
    </template>
  </main>
</template>
