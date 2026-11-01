<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import DepartmentPicker from '../components/DepartmentPicker.vue'
import InterestPicker from '../components/InterestPicker.vue'

const router = useRouter()
const meta = ref({ departments: [], interests: [], analyzer: '' })
const form = ref(null)
const message = ref('')

onMounted(async () => {
  ;[meta.value, form.value] = await Promise.all([api.meta(), api.user()])
})

async function save() {
  const { name, department, grade, interests } = form.value
  try {
    await api.updateUser({ name, department, grade, interests })
    message.value = '저장했어요'
  } catch (failure) {
    message.value = failure.message
  }
}

async function leave() {
  await api.logout()
  router.push('/start')
}
</script>

<template>
  <header class="head">
    <h1 class="title-lg">내 정보</h1>
    <p class="muted">{{ meta.analyzer !== 'rules' ? `AI 분석 사용 중 · ${meta.model}` : '규칙 기반 분석 사용 중 · AI 키 미설정' }}</p>
  </header>
  <form v-if="form" class="main" @submit.prevent="save">
    <div class="card">
      <div class="field">
        <label for="me-name">이름</label>
        <input id="me-name" v-model="form.name" class="input" required maxlength="30" />
      </div>
      <div class="field">
        <label for="me-department">학과</label>
        <DepartmentPicker v-model="form.department" :departments="meta.departments" input-id="me-department" />
      </div>
      <div class="field">
        <label for="me-grade">학년</label>
        <select id="me-grade" v-model.number="form.grade" class="input">
          <option v-for="item in 5" :key="item" :value="item">{{ item }}학년</option>
        </select>
      </div>
    </div>
    <InterestPicker v-model="form.interests" :options="meta.interests" />
    <p v-if="message" class="muted" role="status">{{ message }}</p>
    <button class="btn" :disabled="!form.department">저장</button>
    <button type="button" class="btn btn-line" @click="leave">로그아웃</button>
  </form>
</template>
