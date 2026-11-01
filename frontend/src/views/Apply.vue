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
      <p class="small">프로필과 공지 내용으로 채웠어요. 틀린 부분은 고칠 수 있어요.</p>
    </section>

    <form class="card" @submit.prevent="save(submitted ? 'submitted' : 'draft', '저장했어요')">
      <div v-for="field in draft.fields" :key="field.key" class="field">
        <label :for="`apply-${field.key}`">{{ field.label }}<template v-if="!field.auto"> · 직접 입력</template></label>
        <textarea v-if="field.multiline" :id="`apply-${field.key}`" v-model="field.value" class="input textarea" rows="4" maxlength="2000"></textarea>
        <input v-else :id="`apply-${field.key}`" v-model="field.value" class="input" maxlength="2000" />
      </div>
      <button class="btn btn-line btn-small" :disabled="busy">초안 저장</button>
    </form>

    <section class="card">
      <span class="label-strong">신청 방법</span>
      <p class="muted">{{ draft.how_to_apply || '공지 원문에서 신청 방법을 확인해 주세요' }}</p>
      <p v-if="draft.deadline" class="reason" style="color: var(--due)">{{ longDate(draft.deadline) }} 마감</p>
      <p class="small">공지비서는 대신 제출하지 않아요. 내용을 확인한 뒤 직접 신청해 주세요.</p>
      <div class="action-row">
        <button type="button" class="btn btn-line btn-small btn-grow" @click="copy">복사</button>
        <a :href="api.applicationFile(id)" class="btn btn-line btn-small btn-grow">파일로 받기</a>
        <a v-if="draft.url" :href="draft.url" target="_blank" rel="noopener" class="btn btn-line btn-small btn-grow">공지 원문</a>
      </div>
    </section>
    <p v-if="message" class="muted" role="status">{{ message }}</p>
  </main>
  <p v-else-if="message" class="error main" role="alert">{{ message }}</p>
  <footer v-if="draft" class="foot">
    <button v-if="submitted" class="btn btn-grow btn-line" :disabled="busy" @click="save('draft', '신청 전 상태로 되돌렸어요')">신청 완료 취소</button>
    <button v-else class="btn btn-grow" :disabled="busy" @click="save('submitted', '신청 완료로 표시했어요')">직접 신청했어요</button>
  </footer>
</template>
