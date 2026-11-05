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

const missing = computed(() => draft.value?.fields.filter((field) => !field.value) ?? [])
const autoCount = computed(() => draft.value?.fields.filter((field) => field.auto).length ?? 0)
const submitted = computed(() => draft.value?.status === 'submitted')
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

function values() {
  return Object.fromEntries(draft.value.fields.map((field) => [field.key, field.value]))
}

async function save(status, done) {
  busy.value = true
  try {
    draft.value = await api.saveApplication(props.id, { values: values(), status })
    message.value = done
  } catch (failure) {
    message.value = failure.message
  } finally {
    busy.value = false
  }
}

async function copyField(field) {
  try {
    await navigator.clipboard.writeText(field.value)
    message.value = `${field.label}을(를) 복사했어요. ${formName.value}에 붙여 넣어 주세요`
  } catch {
    message.value = '복사하지 못했어요'
  }
}

async function copy() {
  const text = draft.value.fields.map((field) => `${field.label}: ${field.value}`).join('\n')
  try {
    await navigator.clipboard.writeText(text)
    message.value = '복사했어요. 학교 신청 화면에 붙여 넣어 주세요'
  } catch {
    message.value = '복사하지 못했어요. 파일로 받아 주세요'
  }
}
</script>

<template>
  <header class="head back-head">
    <button class="icon-btn" aria-label="뒤로" @click="router.back()"><Icon name="back" :size="22" /></button>
    <div v-if="draft" class="inner">
      <span class="eyebrow">신청서 초안</span>
      <h1 class="title-sm">{{ draft.title }}</h1>
    </div>
  </header>
  <main v-if="draft" class="main">
    <section class="summary">
      <span class="summary-title"><Icon name="spark" :size="16" :width="2.2" />{{ draft.total }}개 항목 중 {{ autoCount }}개를 채웠어요</span>
      <p class="small">{{ formUrl ? `${formName}에 옮겨 적을 내용을` : '신청할 때 쓸 내용을' }} 프로필과 공지로 미리 채워 뒀어요. 칸마다 복사할 수 있어요.</p>
    </section>

    <section class="card">
      <span class="label-strong">신청 방법</span>
      <p class="muted wrap-anywhere">{{ howTo }}</p>
      <p v-if="draft.deadline" class="reason" style="color: var(--due)">{{ longDate(draft.deadline) }} 마감</p>
      <a v-if="formUrl" :href="formUrl" target="_blank" rel="noopener" class="btn btn-small">{{ formName }} 열기</a>
      <p class="small">공지비서는 대신 제출하지 않아요. 아래 내용을 복사해 {{ formUrl ? formName : '신청 화면' }}에 붙여 넣고 직접 신청해 주세요.</p>
    </section>

    <form class="card" @submit.prevent="save(submitted ? 'submitted' : 'draft', '저장했어요')">
      <div v-for="field in draft.fields" :key="field.key" class="field">
        <div class="field-head">
          <label :for="`apply-${field.key}`">{{ field.label }}<template v-if="!field.auto"> · 직접 입력</template></label>
          <button v-if="field.value" type="button" class="link-btn" @click="copyField(field)">복사</button>
        </div>
        <textarea v-if="field.multiline" :id="`apply-${field.key}`" v-model="field.value" class="input textarea" rows="4" maxlength="2000"></textarea>
        <input v-else :id="`apply-${field.key}`" v-model="field.value" class="input" maxlength="2000" />
      </div>
      <button class="btn btn-line btn-small" :disabled="busy">초안 저장</button>
      <div class="action-row">
        <button type="button" class="btn btn-line btn-small btn-grow" @click="copy">전체 복사</button>
        <a :href="api.applicationFile(id)" class="btn btn-line btn-small btn-grow">파일로 받기</a>
        <a v-if="draft.url" :href="draft.url" target="_blank" rel="noopener" class="btn btn-line btn-small btn-grow">공지 원문</a>
      </div>
    </form>

    <p v-if="message" class="muted" role="status">{{ message }}</p>
  </main>
  <p v-else-if="message" class="error main" role="alert">{{ message }}</p>
  <footer v-if="draft" class="foot">
    <button v-if="submitted" class="btn btn-grow btn-line" :disabled="busy" @click="save('draft', '신청 전 상태로 되돌렸어요')">신청 완료 취소</button>
    <button v-else class="btn btn-grow" :disabled="busy" @click="save('submitted', '신청 완료로 표시했어요')">직접 신청했어요</button>
  </footer>
</template>
