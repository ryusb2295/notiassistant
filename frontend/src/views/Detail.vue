<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import CardNews from '../components/CardNews.vue'
import Icon from '../components/Icon.vue'
import SkeletonCards from '../components/SkeletonCards.vue'
import { dDayLabel, longDate, shortDate } from '../format'

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()
const notice = ref(null)
const error = ref('')
const busy = ref(false)
const reporting = ref(false)
const reported = ref('')

const REPORTS = [
  ['wrong_match', '해당 안 되는데 떴어요'],
  ['wrong_hide', '해당되는데 숨겨졌어요'],
  ['wrong_info', '요약이나 마감이 틀렸어요'],
]

async function report(kind) {
  try {
    await api.feedback(props.id, kind)
    reported.value = '알려주셔서 고마워요. 판정을 고치는 데 쓸게요'
  } catch (failure) {
    reported.value = failure.message
  } finally {
    reporting.value = false
  }
}

const STATUS = { read: '읽음', unsupported: '지원하지 않는 형식', failed: '읽기 실패', needs_ai: 'AI 연결 시 읽기 가능', personal: '개인정보 보호로 분석 제외' }
const isAi = computed(() => notice.value && notice.value.analyzer !== 'rules')
const isOffice = computed(() => notice.value?.analyzer === 'admin')

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
    <SkeletonCards v-if="!notice && !error" :count="3" />
    <template v-if="notice">
      <CardNews v-if="isOffice" :title="notice.title" :deadline="notice.deadline" :audience="notice.audience"
        :benefit="notice.benefit || ''" :how="notice.how_to_apply || ''" />
      <section class="summary">
        <div class="summary-head">
          <span class="summary-title"><Icon name="spark" :size="16" :width="2.2" />{{ isOffice ? '공지 요약' : isAi ? 'AI 요약' : '자동 추출' }}</span>
          <span class="small">{{ isOffice ? '행정실 확인' : isAi ? notice.found_in.join(', ') + '에서 추출' : '규칙 기반 · AI 미사용' }}</span>
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

      <section class="report">
        <button v-if="!reporting && !reported" type="button" class="link-btn" @click="reporting = true"><Icon name="flag" :size="15" />판정이 틀렸어요</button>
        <div v-if="reporting" class="report-options">
          <span class="small">어떤 점이 틀렸나요?</span>
          <button v-for="[kind, label] in REPORTS" :key="kind" type="button" class="toggle-chip" @click="report(kind)">{{ label }}</button>
          <button type="button" class="link-btn" @click="reporting = false">취소</button>
        </div>
        <p v-if="reported" class="small" role="status">{{ reported }}</p>
      </section>

      <RouterLink :to="`/notice/${id}/apply`" class="card apply-link">
        <span><b>신청서 초안 만들기</b><br /><span class="small">내 정보로 자동 입력하고 직접 확인 후 신청해요</span></span>
        <span class="more">시작 ›</span>
      </RouterLink>

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
    <a v-if="notice.url" :href="notice.url" target="_blank" rel="noopener" class="btn btn-line">원문 보기</a>
    <button class="btn btn-grow" :class="{ 'btn-line': notice.saved }" :disabled="busy || !notice.events.length" @click="toggleSchedule">
      <Icon name="calendar" :size="18" />
      {{ !notice.events.length ? '확정된 일정 없음' : notice.saved ? '내 일정에서 빼기' : '내 일정에 추가' }}
    </button>
  </footer>
</template>
