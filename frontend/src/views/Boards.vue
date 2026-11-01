<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'
import SourceList from '../components/SourceList.vue'

const sources = ref([])

onMounted(async () => {
  sources.value = await api.sources()
})
</script>

<template>
  <header class="head">
    <h1 class="title-lg">구독 게시판</h1>
    <p class="muted">구독한 게시판의 공지만 읽고 판정해요</p>
  </header>
  <main class="main">
    <SourceList :sources="sources" />
  </main>
</template>
