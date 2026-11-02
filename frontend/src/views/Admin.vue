<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import CardNews from '../components/CardNews.vue'
import DepartmentPicker from '../components/DepartmentPicker.vue'
import Icon from '../components/Icon.vue'

const SW_GROUP = 'SW중심대학 참여 학과'
const CATEGORIES = ['장학', '취업·진로', '교육·특강', '경진대회', '대외활동', '학사', '행사', '자격증', '기타']

const router = useRouter()
const departments = ref([])
const maxYears = ref(4)
const published = ref([])
const feedback = ref([])
const upload = ref(null)
const form = ref(null)
const picked = ref('')
const busy = ref(false)
const error = ref('')
const notice = ref('')

const preview = computed(() => form.value && {
  title: form.value.title,
  deadline: form.value.deadline,
  audience: form.value.audience,
  benefit: form.value.benefit,
  how: form.value.how_to_apply,
})

onMounted(async () => {
  try {
    const [meta, list] = await Promise.all([api.meta(), api.adminNotices()])
    departments.value = meta.departments
    maxYears.value = meta.max_years
    published.value = list
    feedback.value = await api.adminFeedback()
  } catch (failure) {
    error.value = failure.message
  }
})

watch(picked, (name) => {
  if (name && !form.value.departments.includes(name)) form.value.departments.push(name)
  if (name) picked.value = ''
})

function toggle(list, value) {
  const index = list.indexOf(value)
  if (index >= 0) list.splice(index, 1)
  else list.push(value)
}

async function onFile(event) {
  const [file] = event.target.files
  if (!file) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await api.adminAnalyze(file)
    upload.value = { file_id: result.file_id, name: result.name, analyzer: result.analyzer }
    form.value = {
      title: result.title,
      ...result.analysis,
      benefit: result.analysis.benefit || '',
      how_to_apply: result.analysis.how_to_apply || '',
      deadline: result.analysis.deadline || '',
      summaryText: result.analysis.summary.join('\n'),
    }
  } catch (failure) {
    error.value = failure.message
  } finally {
    busy.value = false
    event.target.value = ''
  }
}

async function publish() {
  busy.value = true
  error.value = ''
  const { title, summaryText, ...rest } = form.value
  const analysis = {
    ...rest,
    summary: summaryText.split('\n').map((line) => line.trim()).filter(Boolean),
    deadline: rest.deadline || null,
    benefit: rest.benefit || null,
    how_to_apply: rest.how_to_apply || null,
    // 담당자가 고친 마감일이 기준이 되도록 분석된 마감 일정은 뺀다.
    events: rest.events.filter((event) => event.kind !== 'deadline'),
  }
  try {
    const result = await api.adminPublish({
      title,
      analysis,
      upload: { file_id: upload.value.file_id, name: upload.value.name },
    })
    notice.value = `게시했어요. 대상 학생 ${result.notified}명에게 알렸어요`
    form.value = null
    upload.value = null
    published.value = await api.adminNotices()
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
    <div class="inner">
      <h1 class="title-md">행정실 공지 작성</h1>
      <p class="muted">공문을 올리면 대상과 마감을 정리해 드려요</p>
    </div>
  </header>
  <main class="main">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" class="reason" role="status">{{ notice }}</p>

    <label class="upload" :class="{ busy }">
      <input type="file" accept=".hwp,.hwpx,.pdf,.xlsx,.jpg,.jpeg,.png,.webp" :disabled="busy" @change="onFile" />
      <span class="label-strong">{{ busy ? '공문을 읽는 중이에요' : upload ? '다른 파일 올리기' : '공문 파일 올리기' }}</span>
      <span class="small">{{ upload ? upload.name : 'HWP, HWPX, PDF, XLSX, 이미지 · 20MB 이하' }}</span>
    </label>

    <form v-if="form" class="main-flat" @submit.prevent="publish">
      <section class="card">
        <span class="label-strong">{{ upload.analyzer === 'rules' ? '자동 추출 결과' : 'AI 추출 결과' }}</span>
        <p class="small">틀린 부분은 바로 고칠 수 있어요</p>
        <div class="field"><label for="ad-title">공지 제목</label><input id="ad-title" v-model="form.title" class="input" required maxlength="200" /></div>
        <div class="field">
          <label for="ad-category">분류</label>
          <select id="ad-category" v-model="form.category" class="input"><option v-for="item in CATEGORIES" :key="item">{{ item }}</option></select>
        </div>
        <div class="field"><label for="ad-audience">신청 대상</label><input id="ad-audience" v-model="form.audience" class="input" maxlength="300" /></div>
        <div class="field"><label for="ad-deadline">신청 마감</label><input id="ad-deadline" v-model="form.deadline" class="input" type="date" /></div>
        <div class="field"><label for="ad-benefit">혜택</label><input id="ad-benefit" v-model="form.benefit" class="input" maxlength="300" /></div>
        <div class="field"><label for="ad-how">신청 방법</label><input id="ad-how" v-model="form.how_to_apply" class="input" maxlength="300" /></div>
        <div class="field"><label for="ad-summary">요약 (줄마다 한 문장)</label><textarea id="ad-summary" v-model="form.summaryText" class="input textarea" rows="4"></textarea></div>
      </section>

      <section class="card">
        <span class="label-strong">알림 받을 학생</span>
        <p class="small">비워 두면 학과 제한 없이 관심사가 맞는 학생에게 알려요</p>
        <div class="chips">
          <button type="button" class="toggle-chip" :aria-pressed="form.departments.includes(SW_GROUP)" @click="toggle(form.departments, SW_GROUP)">{{ SW_GROUP }}</button>
          <button v-for="item in form.departments.filter((d) => d !== SW_GROUP)" :key="item" type="button" class="chip" :aria-label="`${item} 빼기`" @click="toggle(form.departments, item)">{{ item }} ×</button>
        </div>
        <div class="field">
          <label for="ad-department">학과 추가</label>
          <DepartmentPicker v-model="picked" :departments="departments" input-id="ad-department" />
        </div>
        <div class="field">
          <span class="label">학년</span>
          <div class="chips">
            <button v-for="grade in maxYears" :key="grade" type="button" class="toggle-chip" :aria-pressed="form.grades.includes(grade)" @click="toggle(form.grades, grade)">{{ grade }}학년</button>
          </div>
        </div>
      </section>

      <section class="card">
        <span class="label-strong">카드뉴스 미리보기</span>
        <CardNews v-bind="preview" />
      </section>

      <button class="btn" :disabled="busy || !form.title.trim()">게시하고 대상 학생에게 알리기</button>
    </form>

    <template v-if="feedback.length">
      <span class="section-label">학생 판정 오류 신고 {{ feedback.length }}건</span>
      <RouterLink v-for="item in feedback.slice(0, 10)" :key="item.id" :to="`/notice/${item.notice_id}`" class="card">
        <span class="tag tag-due" style="align-self: flex-start">{{ item.label }}</span>
        <span class="card-title">{{ item.title }}</span>
        <span class="small">{{ item.department || '탈퇴한 학생' }}<template v-if="item.note"> · {{ item.note }}</template></span>
      </RouterLink>
    </template>
    <template v-if="published.length">
      <span class="section-label">게시한 공지</span>
      <RouterLink v-for="item in published" :key="item.id" :to="`/notice/${item.id}`" class="card">
        <span class="card-title">{{ item.title }}</span>
        <span class="small">{{ item.posted_at.replaceAll('-', '.') }} · 알림 {{ item.notified }}명 · 일정 저장 {{ item.saved }}명</span>
      </RouterLink>
    </template>
  </main>
</template>
