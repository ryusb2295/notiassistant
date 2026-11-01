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
const isAdmin = ref(false)

onMounted(async () => {
  const [info, account] = await Promise.all([api.meta(), api.me()])
  meta.value = info
  form.value = account
  isAdmin.value = account.is_admin
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

const panel = ref('')
const currentPassword = ref('')
const newPassword = ref('')
const deletePassword = ref('')
const accountMessage = ref('')

function openPanel(name) {
  panel.value = panel.value === name ? '' : name
  accountMessage.value = ''
}

async function changePassword() {
  try {
    await api.changePassword({ current_password: currentPassword.value, new_password: newPassword.value })
    currentPassword.value = ''
    newPassword.value = ''
    panel.value = ''
    accountMessage.value = '비밀번호를 바꿨어요. 다른 기기는 로그아웃됐어요'
  } catch (failure) {
    accountMessage.value = failure.status === 422 ? '새 비밀번호는 8자 이상 입력해 주세요' : failure.message
  }
}

async function deleteAccount() {
  try {
    await api.deleteAccount(deletePassword.value)
    router.push('/start')
  } catch (failure) {
    accountMessage.value = failure.message
  }
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
    <RouterLink v-if="isAdmin" to="/admin" class="btn btn-line">행정실 공지 작성</RouterLink>
    <section class="card account" aria-label="계정 관리">
      <button type="button" class="link-btn" :aria-expanded="panel === 'password'" @click="openPanel('password')">비밀번호 변경</button>
      <div v-if="panel === 'password'" class="field">
        <label for="current-password">현재 비밀번호</label>
        <input id="current-password" v-model="currentPassword" class="input" type="password" autocomplete="current-password" />
        <label for="new-password">새 비밀번호 (8자 이상)</label>
        <input id="new-password" v-model="newPassword" class="input" type="password" autocomplete="new-password" />
        <button type="button" class="btn btn-small" :disabled="!currentPassword || !newPassword" @click="changePassword">변경하기</button>
      </div>
      <RouterLink to="/privacy" class="link-btn account-link">개인정보 처리 안내</RouterLink>
      <button type="button" class="link-btn danger" :aria-expanded="panel === 'delete'" @click="openPanel('delete')">회원 탈퇴</button>
      <div v-if="panel === 'delete'" class="field">
        <p class="warn">프로필, 구독, 일정, 알림이 모두 삭제되고 되돌릴 수 없어요.</p>
        <label for="delete-password">비밀번호 확인</label>
        <input id="delete-password" v-model="deletePassword" class="input" type="password" autocomplete="current-password" />
        <button type="button" class="btn btn-small btn-danger" :disabled="!deletePassword" @click="deleteAccount">탈퇴하기</button>
      </div>
      <p v-if="accountMessage" class="muted" role="status">{{ accountMessage }}</p>
    </section>
  </form>
</template>
