<script setup>
import { computed } from 'vue'
import { longDate } from '../format'

const props = defineProps({
  title: { type: String, required: true },
  deadline: { type: String, default: null },
  audience: { type: String, default: '' },
  benefit: { type: String, default: '' },
  how: { type: String, default: '' },
})

const rows = computed(() => [
  ['대상', props.audience],
  ['혜택', props.benefit],
  ['신청', props.how],
].filter(([, value]) => value))
</script>

<template>
  <article class="cardnews">
    <span class="cardnews-tag">{{ deadline ? `~ ${longDate(deadline)} 마감` : '행정실 공지' }}</span>
    <h2 class="cardnews-title">{{ title }}</h2>
    <dl class="cardnews-rows">
      <div v-for="[label, value] in rows" :key="label"><dt>{{ label }}</dt><dd>{{ value }}</dd></div>
    </dl>
  </article>
</template>
