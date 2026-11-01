<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import { dDayLabel, longDate, shortDate } from '../format'

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()
const notice = ref(null)
const error = ref('')
const busy = ref(false)

const STATUS = { read: '읽음', unsupported: '지원하지 않는 형식', failed: '읽기 실패', needs_ai: 'AI 연결 시 읽기 가능', personal: '개인정보 보호로 분석 제외' }
const isAi = computed(() => notice.value && notice.value.analyzer !== 'rules')

onMounted(async () => {
  try {
    notice.value = await api.notice(props.id)
  } catch (failure) {
    error.value = failure.message
  }
})

async function toggleSchedule() {
  busy.value = true
  error.value = ''
  try {
    if (notice.value.saved) await api.removeSchedule(props.id)
    else await api.saveSchedule(props.id)
    notice.value.saved = !notice.value.saved
  } catch (failure) {
    error.value = failure.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <header class="head back-head">
    <button class="icon-btn" aria-label="뒤로" @click="router.back()"><Icon name="back" :size="22" /></button>
    <div v-if="notice" class="inner">
      <span class="small">{{ notice.source }} · {{ notice.posted_at.replaceAll('-', '.') }}</span>
      <h1 class="title-md">{{ notice.title }}</h1>
    </div>
  </header>
  <main class="main">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <template v-if="notice">
      <section class="summary">
        <div class="summary-head">
          <span class="summary-title"><Icon name="spark" :size="16" :width="2.2" />{{ isAi ? 'AI 요약' : '자동 추출' }}</span>
          <span class="small">{{ isAi ? notice.found_in.join(', ') + '에서 추출' : '규칙 기반 · AI 미사용' }}</span>
        </div>
        <ul><li v-for="line in notice.summary" :key="line">{{ line }}</li></ul>
      </section>

      <p v-if="notice.skipped_images" class="warn">본문 이미지 {{ notice.skipped_images }}장은 읽지 않았어요. 이미지에만 있는 내용은 원문에서 확인해 주세요.</p>

      <dl class="card rows">
        <div class="row"><dt>분류</dt><dd>{{ notice.category }}</dd></div>
        <div class="row"><dt>대상</dt><dd>{{ notice.audience }}</dd></div>
        <div class="row">
          <dt>신청 마감</dt>
          <dd v-if="notice.deadline" class="due">{{ longDate(notice.deadline) }}<template v-if="notice.d_day >= 0"> · {{ dDayLabel(notice.d_day) }}</template></dd>
          <dd v-else>공지에서 찾지 못했어요</dd>
        </div>
        <div v-if="notice.benefit" class="row"><dt>혜택</dt><dd>{{ notice.benefit }}</dd></div>
        <div v-if="notice.how_to_apply" class="row"><dt>신청 방법</dt><dd>{{ notice.how_to_apply }}</dd></div>
        <div class="row"><dt>판정</dt><dd :class="{ ok: notice.match === 'match' }">{{ notice.reason }}</dd></div>
      </dl>

      <section v-if="notice.attachments.length" class="card">
        <span class="small" style="font-weight: 600">첨부파일</span>
        <RouterLink v-for="file in notice.attachments" :key="file.id" :to="`/file/${file.id}`" class="attachment attachment-link">
          <span class="ext">{{ file.ext }}</span>
          <span class="attachment-name">{{ file.name }}<template v-if="file.status !== 'read'"> · {{ STATUS[file.status] }}</template></span>
          <span class="more">보기 ›</span>
        </RouterLink>
      </section>

      <section v-if="notice.events.length" class="card">
        <span class="small" style="font-weight: 600">일정에 추가될 내용</span>
        <div v-for="event in notice.events" :key="event.title + event.date" class="schedule-line">
          <b :class="{ event: event.kind === 'event' }">{{ shortDate(event.date) }}</b>
          <span style="flex: 1">{{ event.title }}</span>
          <a :href="event.google_url" target="_blank" rel="noopener" class="more">구글 캘린더</a>
        </div>
      </section>
    </template>
  </main>
  <footer v-if="notice" class="foot">
    <a :href="notice.url" target="_blank" rel="noopener" class="btn btn-line">원문 보기</a>
    <button class="btn btn-grow" :class="{ 'btn-line': notice.saved }" :disabled="busy || !notice.events.length" @click="toggleSchedule">
      <Icon name="calendar" :size="18" />
      {{ !notice.events.length ? '확정된 일정 없음' : notice.saved ? '내 일정에서 빼기' : '내 일정에 추가' }}
    </button>
  </footer>
</template>
