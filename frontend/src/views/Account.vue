<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import Icon from '../components/Icon.vue'

const router = useRouter()
const username = ref('')
const currentPassword = ref('')
const newPassword = ref('')
const deletePassword = ref('')
const showDelete = ref(false)
const message = ref('')

onMounted(async () => {
  username.value = (await api.me()).username
})

async function changePassword() {
  try {
    await api.changePassword({ current_password: currentPassword.value, new_password: newPassword.value })
    currentPassword.value = ''
    newPassword.value = ''
    message.value = '비밀번호를 바꿨어요. 다른 기기는 로그아웃됐어요'
  } catch (failure) {
    message.value = failure.status === 422 ? '새 비밀번호는 8자 이상 입력해 주세요' : failure.message
  }
}

async function deleteAccount() {
  try {
    await api.deleteAccount(deletePassword.value)
    router.push('/start')
  } catch (failure) {
    message.value = failure.message
  }
}
</script>

<template>
  <header class="head back-head">
    <button class="icon-btn" aria-label="뒤로" @click="router.back()"><Icon name="back" :size="22" /></button>
    <div class="inner"><h1 class="title-md">계정 관리</h1><p class="muted">아이디 {{ username }}</p></div>
  </header>
  <main class="main">
    <form class="card" @submit.prevent="changePassword">
      <span class="label-strong">비밀번호 변경</span>
      <div class="field">
        <label for="current-password">현재 비밀번호</label>
        <input id="current-password" v-model="currentPassword" class="input" type="password" autocomplete="current-password" />
      </div>
      <div class="field">
        <label for="new-password">새 비밀번호 (8자 이상)</label>
        <input id="new-password" v-model="newPassword" class="input" type="password" autocomplete="new-password" />
      </div>
      <button class="btn btn-small" :disabled="!currentPassword || !newPassword">변경하기</button>
    </form>
    <p v-if="message" class="muted" role="status">{{ message }}</p>
    <section class="card account">
      <button type="button" class="link-btn danger" :aria-expanded="showDelete" @click="showDelete = !showDelete">회원 탈퇴</button>
      <form v-if="showDelete" class="field" @submit.prevent="deleteAccount">
        <p class="warn">프로필, 구독, 일정, 신청서, 알림이 모두 삭제되고 되돌릴 수 없어요.</p>
        <label for="delete-password">비밀번호 확인</label>
        <input id="delete-password" v-model="deletePassword" class="input" type="password" autocomplete="current-password" />
        <button class="btn btn-small btn-danger" :disabled="!deletePassword">탈퇴하기</button>
      </form>
    </section>
  </main>
</template>
