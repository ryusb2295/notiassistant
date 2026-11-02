<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import SkeletonCards from '../components/SkeletonCards.vue'
import { dateTime } from '../format'

const router = useRouter()
const alerts = ref([])
const selected = ref([])
const opened = ref(null)
const detail = ref(null)
const loaded = ref(false)
const error = ref('')

const allSelected = computed(() => alerts.value.length > 0 && selected.value.length === alerts.value.length)

async function load() {
  try {
    alerts.value = await api.alerts()
    selected.value = selected.value.filter((id) => alerts.value.some((alert) => alert.id === id))
  } catch (failure) {
    error.value = failure.message
  } finally {
    loaded.value = true
  }
}

function onKeydown(event) {
  if (event.key === 'Escape') close()
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

function toggleAll() {
  selected.value = allSelected.value ? [] : alerts.value.map((alert) => alert.id)
}

async function markRead() {
  const ids = selected.value.length ? selected.value : undefined
  await api.readAlerts(ids)
  selected.value = []
  await load()
}

async function remove(ids) {
  if (!ids.length) return
  await api.deleteAlerts(ids)
  selected.value = []
  close()
  await load()
}

async function open(alert) {
  opened.value = alert
  detail.value = null
  if (!alert.read) {
    alert.read = 1
    api.readAlerts([alert.id])
  }
  try {
    detail.value = await api.notice(alert.notice_id)
  } catch {
    detail.value = { summary: [] }
  }
}

function close() {
  opened.value = null
}

function goToNotice() {
  router.push(`/notice/${opened.value.notice_id}`)
}
</script>

<template>
  <header class="head alert-head">
    <div class="head-row"><h1 class="title-md">알림함</h1><span v-if="selected.length" class="small">{{ selected.length }}개 선택</span></div>
    <div class="alert-actions">
      <button :aria-pressed="allSelected" @click="toggleAll"><Icon name="check" :size="20" />전체선택</button>
      <button :disabled="!selected.length" @click="remove(selected)"><Icon name="trash" :size="20" />삭제</button>
      <button :disabled="!alerts.length" @click="markRead"><Icon name="mail" :size="20" />읽음</button>
      <button @click="load"><Icon name="refresh" :size="20" />새로고침</button>
    </div>
  </header>
  <main class="alert-list">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div v-for="alert in alerts" :key="alert.id" class="alert-item">
      <input v-model="selected" type="checkbox" :value="alert.id" :aria-label="`${alert.body} 선택`" />
      <button class="alert-open" :class="{ unread: !alert.read }" @click="open(alert)">
        <span class="alert-label">{{ alert.title }}</span>
        <span class="alert-body">{{ alert.body }}</span>
        <span class="small">{{ dateTime(alert.created_at) }}</span>
      </button>
    </div>
    <SkeletonCards v-if="!loaded" :count="4" />
    <p v-if="loaded && !alerts.length" class="empty">아직 알림이 없어요</p>
  </main>

  <div v-if="opened" class="sheet-back" @click.self="close">
    <section class="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title">
      <button class="sheet-close" @click="close">닫기 ×</button>
      <div class="sheet-body">
        <div class="sheet-top">
          <h2 id="sheet-title">{{ opened.body }}</h2>
          <button class="icon-btn" aria-label="알림 삭제" @click="remove([opened.id])"><Icon name="trash" :size="22" /></button>
        </div>
        <p class="small">발송 : {{ dateTime(opened.created_at) }}</p>
        <p class="sheet-sender">발신자 : {{ opened.sender }}</p>
        <ul v-if="detail?.summary?.length" class="sheet-summary"><li v-for="line in detail.summary" :key="line">{{ line }}</li></ul>
        <button class="btn" @click="goToNotice">공지 자세히 보기</button>
      </div>
    </section>
  </div>
</template>
