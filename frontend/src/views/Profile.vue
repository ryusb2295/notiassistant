<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import Avatar from '../components/Avatar.vue'
import DepartmentPicker from '../components/DepartmentPicker.vue'
import Icon from '../components/Icon.vue'
import InterestPicker from '../components/InterestPicker.vue'

const router = useRouter()
const meta = ref({ departments: [], interests: [] })
const form = ref(null)
const message = ref('')
const photoSrc = ref('')

function refreshPhoto(account) {
  photoSrc.value = account.has_avatar ? api.avatarUrl(Date.now()) : ''
}

async function onPhoto(event) {
  const [file] = event.target.files
  event.target.value = ''
  if (!file) return
  try {
    await api.uploadAvatar(file)
    photoSrc.value = api.avatarUrl(Date.now())
    message.value = '프로필 사진을 바꿨어요'
  } catch (failure) {
    message.value = failure.message
  }
}

async function removePhoto() {
  await api.deleteAvatar()
  photoSrc.value = ''
  message.value = '프로필 사진을 지웠어요'
}

onMounted(async () => {
  ;[meta.value, form.value] = await Promise.all([api.meta(), api.me()])
  refreshPhoto(form.value)
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
</script>

<template>
  <header class="head back-head">
    <button class="icon-btn" aria-label="뒤로" @click="router.back()"><Icon name="back" :size="22" /></button>
    <div class="inner"><h1 class="title-md">프로필 수정</h1></div>
  </header>
  <form v-if="form" class="main" @submit.prevent="save">
    <section class="card photo">
      <Avatar :src="photoSrc" :size="84" />
      <div class="photo-actions">
        <label class="btn btn-line btn-small">
          <input type="file" accept="image/jpeg,image/png,image/webp" class="hidden-input" @change="onPhoto" />사진 선택
        </label>
        <button v-if="photoSrc" type="button" class="link-btn danger" @click="removePhoto">사진 삭제</button>
        <span class="small">JPG, PNG, WEBP · 3MB 이하</span>
      </div>
    </section>
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
  </form>
</template>
