<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import DepartmentPicker from '../components/DepartmentPicker.vue'
import InterestPicker from '../components/InterestPicker.vue'

const router = useRouter()
const meta = ref({ departments: [], interests: [] })
const mode = ref('login')
const username = ref('')
const password = ref('')
const name = ref('')
const department = ref('')
const grade = ref(3)
// 학과마다 수업 연한이 달라서(건축학 5년, 약학 6년 등) 선택지와 현재 값을 맞춘다.
const maxGrade = computed(() => meta.value.departments.find((d) => d.name === department.value)?.years ?? 4)
watch(maxGrade, (years) => { if (grade.value > years) grade.value = years })
const interests = ref([])
const agreed = ref(false)
const error = ref('')
const busy = ref(false)

const isSignup = computed(() => mode.value === 'signup')
const ready = computed(
  () => username.value && password.value && (!isSignup.value || (name.value.trim() && department.value && agreed.value)),
)

onMounted(async () => {
  try {
    meta.value = await api.meta()
  } catch (failure) {
    error.value = failure.message
  }
})

function switchMode(next) {
  mode.value = next
  error.value = ''
}

async function submit() {
  busy.value = true
  error.value = ''
  try {
    if (isSignup.value) {
      await api.signup({
        username: username.value,
        password: password.value,
        name: name.value.trim(),
        department: department.value,
        grade: grade.value,
        interests: interests.value,
        agreed: agreed.value,
      })
      router.push('/recommend')
    } else {
      await api.login({ username: username.value, password: password.value })
      router.push('/')
    }
  } catch (failure) {
    error.value = failure.status === 422 && !failure.detail ? '아이디는 4자 이상, 비밀번호는 8자 이상 입력해 주세요' : failure.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <header class="head">
    <span class="eyebrow">{{ isSignup ? '가입 1/2 단계 · 내 정보' : '공지비서' }}</span>
    <h1 class="title-lg">학과만 입력하면<br />해당되는 공지만 골라 드려요</h1>
    <p class="muted">첨부파일까지 읽고 학과와 학년 조건을 비교해요</p>
  </header>
  <form class="main" @submit.prevent="submit">
    <div class="card">
      <div class="field">
        <label for="username">아이디</label>
        <input id="username" v-model.trim="username" class="input" required maxlength="30" autocomplete="username" autocapitalize="none" />
      </div>
      <div class="field">
        <label for="password">비밀번호{{ isSignup ? ' (8자 이상)' : '' }}</label>
        <input id="password" v-model="password" class="input" type="password" required maxlength="128"
          :autocomplete="isSignup ? 'new-password' : 'current-password'" />
      </div>
    </div>
    <template v-if="isSignup">
      <div class="card">
        <div class="field">
          <label for="name">이름</label>
          <input id="name" v-model="name" class="input" required maxlength="30" autocomplete="off" />
        </div>
        <div class="field">
          <label for="department">학과</label>
          <DepartmentPicker v-model="department" :departments="meta.departments" input-id="department" />
        </div>
        <div class="field">
          <label for="grade">학년</label>
          <select id="grade" v-model.number="grade" class="input">
            <option v-for="item in maxGrade" :key="item" :value="item">{{ item }}학년</option>
          </select>
        </div>
      </div>
      <InterestPicker v-model="interests" :options="meta.interests" />
      <label class="consent">
        <input v-model="agreed" type="checkbox" />
        <span>개인정보 수집·이용에 동의합니다 <RouterLink to="/privacy" class="more">자세히 보기</RouterLink></span>
      </label>
    </template>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <button class="btn" :disabled="busy || !ready">{{ isSignup ? '다음' : '로그인' }}</button>
    <p class="auth-switch">
      {{ isSignup ? '이미 계정이 있나요?' : '아직 계정이 없나요?' }}
      <button type="button" class="link-btn" @click="switchMode(isSignup ? 'login' : 'signup')">{{ isSignup ? '로그인' : '회원가입' }}</button>
    </p>
  </form>
</template>
