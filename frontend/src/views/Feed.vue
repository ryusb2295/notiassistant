<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'
import BoardChips from '../components/BoardChips.vue'
import Icon from '../components/Icon.vue'
import PagedList from '../components/PagedList.vue'
import SkeletonCards from '../components/SkeletonCards.vue'
import { ago } from '../format'

const PULL_LIMIT = 70

const user = ref(null)
const feed = ref(null)
const sources = ref([])
const showOthers = ref(false)
const showHidden = ref(false)
const filter = ref(null)
const query = ref('')
const loading = ref(false)
const pull = ref(0)
const error = ref('')

const subscribed = computed(() => sources.value.filter((s) => s.subscribed))
const filterName = computed(() => subscribed.value.find((s) => s.id === filter.value)?.name)
const searching = computed(() => query.value.trim().length > 0)
const resultCount = computed(() => feed.value
  ? feed.value.urgent.length + feed.value.mine.length + feed.value.others.length
  : 0)

async function load() {
  loading.value = true
  error.value = ''
  try {
    feed.value = await api.feed(filter.value, query.value.trim())
  } catch (failure) {
    error.value = failure.message
  } finally {
    loading.value = false
  }
}

// 칩을 고르면 그 게시판 공지만, 전체를 고르면 모든 구독 게시판을 보여준다.
function setFilter(id) {
  filter.value = id
  showOthers.value = Boolean(id)
  load()
}

let timer = null
function onSearch(event) {
  query.value = event.target.value
  clearTimeout(timer)
  timer = setTimeout(load, 300)
}

function clearSearch() {
  query.value = ''
  load()
}

// 맨 위에서 아래로 당기면 새로고침한다.
let startY = null
function onTouchStart(event) {
  startY = window.scrollY === 0 ? event.touches[0].clientY : null
}
function onTouchMove(event) {
  if (startY === null) return
  pull.value = Math.max(0, Math.min(PULL_LIMIT * 1.4, event.touches[0].clientY - startY))
}
function onTouchEnd() {
  if (pull.value >= PULL_LIMIT) load()
  pull.value = 0
  startY = null
}

onMounted(async () => {
  window.addEventListener('touchstart', onTouchStart, { passive: true })
  window.addEventListener('touchmove', onTouchMove, { passive: true })
  window.addEventListener('touchend', onTouchEnd)
  try {
    ;[user.value, sources.value] = await Promise.all([api.user(), api.sources()])
  } catch (failure) {
    error.value = failure.message
  }
  await load()
})

onBeforeUnmount(() => {
  window.removeEventListener('touchstart', onTouchStart)
  window.removeEventListener('touchmove', onTouchMove)
  window.removeEventListener('touchend', onTouchEnd)
  clearTimeout(timer)
})
</script>

<template>
  <div v-if="pull" class="pull-hint" :style="{ height: `${pull}px` }">{{ pull >= PULL_LIMIT ? '놓으면 새로고침' : '당겨서 새로고침' }}</div>
  <header class="head">
    <div class="head-row">
      <span class="brand"><span class="brand-mark"><Icon name="logo" :size="16" :width="2.2" style="color: #fff" /></span>공지비서</span>
      <button class="icon-btn" aria-label="새로고침" :disabled="loading" @click="load">
        <Icon name="refresh" :size="21" :class="{ spin: loading }" />
      </button>
    </div>
    <div v-if="feed && user && !searching">
      <p class="muted">{{ user.name }}님, 최근 7일 새 공지 {{ feed.new_count }}개를 읽었어요</p>
      <h1 class="title-lg">해당되는 공지는 <span class="accent">{{ feed.match_count }}개</span>예요</h1>
    </div>
    <label class="search">
      <Icon name="search" :size="18" />
      <input :value="query" type="search" placeholder="공지 검색 (예: 해커톤, 장학)" aria-label="공지 검색" @input="onSearch" />
      <button v-if="searching" type="button" class="search-clear" aria-label="검색어 지우기" @click="clearSearch">×</button>
    </label>
    <BoardChips :sources="subscribed" :model-value="filter" @update:model-value="setFilter" />
    <p v-if="feed" class="updated small">
      <Icon name="refresh" :size="12" />공지 업데이트 {{ ago(feed.last_crawl) }}
    </p>
  </header>
  <main class="main">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div v-if="filter" class="filter-bar">
      <span><b>{{ filterName }}</b> 공지만 보는 중</span>
      <button class="link-btn" @click="setFilter(null)">전체 보기</button>
    </div>
    <p v-if="searching && feed" class="section-label" role="status">"{{ query.trim() }}" 전체 게시판 검색 결과 {{ resultCount }}건</p>
    <SkeletonCards v-if="!feed" :count="4" />
    <template v-else>
      <template v-if="feed.urgent.length">
        <span class="section-label">마감 임박</span>
        <PagedList :notices="feed.urgent" variant="urgent" label="마감 임박" :size="4" />
      </template>
      <template v-if="feed.mine.length">
        <span class="section-label">나에게 해당</span>
        <PagedList :notices="feed.mine" variant="mine" label="나에게 해당" />
      </template>
      <p v-if="!feed.match_count && !searching" class="empty">지금 해당되는 공지가 없어요</p>
      <template v-if="feed.others.length">
        <div v-if="!searching" class="toggle-row">
          <span class="section-label">그 외 대상 제한 없는 공지 {{ feed.others.length }}개</span>
          <button class="link-btn" :aria-expanded="showOthers" @click="showOthers = !showOthers">{{ showOthers ? '접기' : '펼치기' }}</button>
        </div>
        <PagedList v-if="showOthers || searching" :notices="feed.others" label="그 외 공지" />
      </template>
      <p v-if="searching && !resultCount" class="empty">검색 결과가 없어요</p>
      <template v-if="feed.hidden.length && !searching">
        <div class="toggle-row">
          <span class="small" style="padding: 0 4px">대상이 아니라서 숨긴 공지 {{ feed.hidden.length }}개</span>
          <button class="link-btn" :aria-expanded="showHidden" @click="showHidden = !showHidden">{{ showHidden ? '접기' : '보기' }}</button>
        </div>
        <template v-if="showHidden">
          <p class="small hidden-note">판정이 틀렸다면 공지를 열고 "판정이 틀렸어요"를 눌러 주세요.</p>
          <PagedList :notices="feed.hidden" label="숨긴 공지" />
        </template>
      </template>
    </template>
  </main>
</template>
