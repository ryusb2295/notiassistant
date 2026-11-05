<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, MOCK } from '../api'
import Icon from '../components/Icon.vue'

const props = defineProps({ fileId: { type: String, required: true } })
const router = useRouter()
const file = ref(null)
const text = ref(null)
const showText = ref(false)
const error = ref('')
const loading = ref(false)
const imageReady = ref(false)

const src = computed(() => api.attachmentFile(props.fileId))
const canText = computed(() => file.value && (file.value.preview === 'text' || file.value.preview === 'pdf'))

onMounted(async () => {
  try {
    file.value = await api.attachment(props.fileId)
    if (file.value.preview === 'text') await loadText()
  } catch (failure) {
    error.value = failure.message
  }
})

async function loadText() {
  showText.value = true
  if (text.value !== null) return
  loading.value = true
  error.value = ''
  try {
    text.value = (await api.attachmentText(props.fileId)).text
  } catch (failure) {
    error.value = failure.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <header class="head back-head">
    <button class="icon-btn" aria-label="뒤로" @click="router.back()"><Icon name="back" :size="22" /></button>
    <div v-if="file" class="inner">
      <span class="ext" style="align-self: flex-start">{{ file.ext }}</span>
      <h1 class="title-sm">{{ file.name }}</h1>
    </div>
  </header>
  <main class="main">
    <div v-if="file?.preview === 'pdf'" class="chips">
      <button class="toggle-chip" :aria-pressed="!showText" @click="showText = false">원본 보기</button>
      <button class="toggle-chip" :aria-pressed="showText" @click="loadText">텍스트로 보기</button>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <template v-if="file">
      <iframe v-if="file.preview === 'pdf' && !showText" :src="src" :title="file.name" class="viewer-frame"></iframe>
      <template v-else-if="file.preview === 'image'">
        <p v-if="!imageReady" class="empty">이미지를 불러오는 중이에요</p>
        <img :src="src" :alt="file.name" class="viewer-image" @load="imageReady = true" />
      </template>
      <div v-else-if="canText && showText" class="card">
        <p v-if="loading" class="muted">내용을 읽는 중이에요</p>
        <p v-else-if="text" class="viewer-text">{{ text }}</p>
        <p v-else-if="text !== null" class="muted">글자를 찾지 못했어요. 스캔한 문서일 수 있으니 파일을 받아서 확인해 주세요.</p>
      </div>
      <p v-else-if="file.personal" class="empty">{{ MOCK ? '목업 버전이라 첨부는 학교 사이트에서 확인해 주세요.' : '개인정보가 있을 수 있어 학교 사이트에서만 볼 수 있어요.' }}</p>
      <p v-else-if="file.preview === 'none'" class="empty">이 형식은 미리 볼 수 없어요. 파일을 받아서 확인해 주세요.</p>
    </template>
  </main>
  <footer v-if="file" class="foot">
    <a v-if="!file.url.startsWith('upload:')" :href="file.url" target="_blank" rel="noopener" class="btn btn-line" :class="{ 'btn-grow': file.personal }">학교 사이트</a>
    <a v-if="!file.personal" :href="`${src}?download=true`" class="btn btn-grow">다운로드</a>
  </footer>
</template>
