<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import { longDate } from '../format'

const props = defineProps({ id: { type: String, required: true } })
const router = useRouter()
const draft = ref(null)
const message = ref('')
const busy = ref(false)

const submitted = computed(() => draft.value?.status === 'submitted')
const planned = computed(() => draft.value?.status === 'draft')
// 신청 방법에 링크가 있으면 버튼으로 빼고, 본문에는 긴 주소 대신 설명만 남긴다.
const formUrl = computed(() => draft.value?.how_to_apply?.match(/https?:\/\/[^\s)\]]+/)?.[0] ?? '')
const formName = computed(() => (/forms\.gle|docs\.google\.com\/forms/.test(formUrl.value) ? '구글 폼' : '신청 페이지'))
const howTo = computed(() => {
  const text = draft.value?.how_to_apply
  if (!text) return '공지 원문에서 신청 방법을 확인해 주세요'
  return formUrl.value ? text.replace(formUrl.value, '').replace(/\(\s*\)/g, '').replace(/\s{2,}/g, ' ').trim() : text
})

onMounted(async () => {
  try {
    draft.value = await api.application(props.id)
  } catch (failure) {
    message.value = failure.message
  }
})

async function save(status, done) {
  busy.value = true
  try {
    // 예전에 직접 입력해 둔 값은 지우지 않고 상태만 바꾼다.
    const values = Object.fromEntries(draft.value.fields.filter((f) => f.value && !f.auto).map((f) => [f.key, f.value]))
    draft.value = await api.saveApplication(props.id, { values, status })
    message.value = done
  } catch (failure) {
    message.value = failure.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <header class="head back-head">
    <button class="icon-btn" aria-label="뒤로" @click="router.back()"><Icon name="back" :size="22" /></button>
    <div v-if="draft" class="inner">
      <span class="eyebrow">신청하기</span>
      <h1 class="title-sm">{{ draft.title }}</h1>
    </div>
  </header>
  <main v-if="draft" class="main">
    <section class="card">
      <div class="card-top">
        <span class="label-strong">신청 방법</span>
        <span v-if="submitted" class="tag tag-info">신청 완료</span>
        <span v-else-if="planned" class="tag">신청 예정</span>
      </div>
      <p class="muted wrap-anywhere">{{ howTo }}</p>
      <p v-if="draft.deadline" class="reason" style="color: var(--due)">{{ longDate(draft.deadline) }} 마감</p>
      <a v-if="formUrl" :href="formUrl" target="_blank" rel="noopener" class="btn btn-small">{{ formName }} 열기</a>
      <a v-if="draft.url" :href="draft.url" target="_blank" rel="noopener" class="btn btn-line btn-small">공지 원문</a>
      <p class="small">공지비서는 대신 제출하지 않아요. 직접 신청한 뒤 아래에서 신청 완료로 표시하면 신청 현황에 모여요.</p>
    </section>
    <p v-if="message" class="muted" role="status">{{ message }}</p>
  </main>
  <p v-else-if="message" class="error main" role="alert">{{ message }}</p>
  <footer v-if="draft" class="foot">
    <button v-if="submitted" class="btn btn-grow btn-line" :disabled="busy" @click="save('draft', '신청 예정으로 되돌렸어요')">신청 완료 취소</button>
    <template v-else>
      <button v-if="!planned" class="btn btn-line" :disabled="busy" @click="save('draft', '신청 현황에 담았어요')">나중에 신청</button>
      <button class="btn btn-grow" :disabled="busy" @click="save('submitted', '신청 완료로 표시했어요')">신청했어요</button>
    </template>
  </footer>
</template>
