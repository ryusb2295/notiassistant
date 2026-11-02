<script setup>
import { computed, ref, watch } from 'vue'
import NoticeCard from './NoticeCard.vue'

const props = defineProps({
  notices: { type: Array, required: true },
  variant: { type: String, default: '' },
  label: { type: String, required: true },
  size: { type: Number, default: 6 },
})

const page = ref(1)
const pages = computed(() => Math.max(1, Math.ceil(props.notices.length / props.size)))
const shown = computed(() => props.notices.slice((page.value - 1) * props.size, page.value * props.size))

// 목록이 바뀌면(게시판 필터 등) 첫 페이지로 돌아간다.
watch(() => props.notices, () => { page.value = 1 })
</script>

<template>
  <NoticeCard v-for="notice in shown" :key="notice.id" :notice="notice" :variant="variant" />
  <nav v-if="pages > 1" class="pager" :aria-label="`${label} 페이지`">
    <button :disabled="page === 1" aria-label="이전 페이지" @click="page -= 1">‹</button>
    <button v-for="n in pages" :key="n" :aria-current="n === page ? 'page' : undefined" :class="{ on: n === page }" @click="page = n">{{ n }}</button>
    <button :disabled="page === pages" aria-label="다음 페이지" @click="page += 1">›</button>
  </nav>
</template>
