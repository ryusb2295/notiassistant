<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import SourceList from '../components/SourceList.vue'

const sources = ref([])
const user = ref(null)
const count = computed(() => sources.value.filter((s) => s.recommended).length)
const chosen = computed(() => sources.value.filter((s) => s.subscribed && s.kind !== 'base').length)

onMounted(async () => {
  ;[user.value, sources.value] = await Promise.all([api.user(), api.sources()])
  await Promise.all(
    sources.value
      .filter((s) => s.recommended && s.id !== 'rise')
      .map((s) => {
        s.subscribed = true
        return api.subscribe(s.id)
      }),
  )
})
</script>

<template>
  <header class="head">
    <span class="eyebrow">가입 2/2 단계 · 사업단 찾기</span>
    <h1 v-if="user" class="title-lg">{{ user.department }}에 맞는<br />게시판 <span class="accent">{{ count }}곳</span>을 찾았어요</h1>
    <p class="muted">구독하면 이 게시판 공지도 읽고 정리해 드려요</p>
  </header>
  <main class="main">
    <SourceList :sources="sources" />
  </main>
  <footer class="foot">
    <RouterLink to="/" class="btn btn-grow">{{ chosen }}곳 구독하고 시작하기</RouterLink>
  </footer>
</template>
