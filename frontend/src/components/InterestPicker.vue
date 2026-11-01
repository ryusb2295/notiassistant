<script setup>
import Icon from './Icon.vue'

const props = defineProps({
  modelValue: { type: Array, required: true },
  options: { type: Array, required: true },
})
const emit = defineEmits(['update:modelValue'])

const DETAILS = {
  장학: { icon: 'scholarship', text: '장학금 · 마일리지' },
  '취업·진로': { icon: 'briefcase', text: '채용 · 컨설팅 · 인턴' },
  '교육·특강': { icon: 'book', text: '캠프 · 부트캠프 · 특강' },
  경진대회: { icon: 'trophy', text: '공모전 · 해커톤' },
  대외활동: { icon: 'people', text: '봉사 · 서포터즈' },
  자격증: { icon: 'badge', text: '인증 · 시험 지원' },
}

function toggle(item) {
  emit('update:modelValue', props.modelValue.includes(item)
    ? props.modelValue.filter((value) => value !== item)
    : [...props.modelValue, item])
}
</script>

<template>
  <section class="card" aria-labelledby="interest-title">
    <div class="interest-head">
      <span id="interest-title" class="label-strong">관심사</span>
      <span class="small">{{ modelValue.length ? `${modelValue.length}개 선택` : '선택 사항' }}</span>
    </div>
    <p class="small">고른 분야의 공지를 내 공지로 알려드려요</p>
    <div class="interest-grid">
      <button v-for="item in options" :key="item" type="button" class="interest"
        :class="{ on: modelValue.includes(item) }" :aria-pressed="modelValue.includes(item)" @click="toggle(item)">
        <span class="interest-icon"><Icon :name="DETAILS[item]?.icon || 'spark'" :size="20" /></span>
        <span class="interest-body">
          <span class="interest-name">{{ item }}</span>
          <span class="interest-text">{{ DETAILS[item]?.text }}</span>
        </span>
        <span class="interest-check"><Icon v-if="modelValue.includes(item)" name="check" :size="13" :width="3" /></span>
      </button>
    </div>
  </section>
</template>
