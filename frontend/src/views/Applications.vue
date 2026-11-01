<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import { longDate } from '../format'

const router = useRouter()
const items = ref(null)
const error = ref('')

onMounted(async () => {
  try {
    items.value = await api.applications()
  } catch (failure) {
    error.value = failure.message
  }
})
</script>

<template>
  <header class="head back-head">
    <button class="icon-btn" aria-label="뒤로" @click="router.back()"><Icon name="back" :size="22" /></button>
    <div class="inner"><h1 class="title-md">내 신청서</h1></div>
  </header>
  <main class="main">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <RouterLink v-for="item in items" :key="item.notice_id" :to="`/notice/${item.notice_id}/apply`" class="card">
      <div class="card-top">
        <span class="small">{{ item.deadline ? `${longDate(item.deadline)} 마감` : '마감일 없음' }}</span>
        <span class="tag" :class="{ 'tag-info': item.status === 'submitted' }">{{ item.status === 'submitted' ? '신청 완료' : '작성 중' }}</span>
      </div>
      <span class="card-title">{{ item.title }}</span>
    </RouterLink>
    <p v-if="items && !items.length" class="empty">공지 상세에서 신청서 초안을 만들면 여기에 모여요</p>
  </main>
</template>
