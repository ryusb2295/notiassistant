<script setup>
import { computed } from 'vue'
import Icon from './Icon.vue'
import { dDayLabel, shortDate } from '../format'

const props = defineProps({
  notice: { type: Object, required: true },
  variant: { type: String, default: '' },
})

const tag = computed(() => {
  const { d_day: days, deadline, category } = props.notice
  if (days === null) return category
  return props.variant === 'urgent' ? `${dDayLabel(days)} · ${shortDate(deadline)} 마감` : dDayLabel(days)
})
</script>

<template>
  <RouterLink :to="`/notice/${notice.id}`" class="card card-link" :class="variant && `card-${variant}`">
    <div class="card-top">
      <span class="small">{{ notice.source }} · {{ notice.posted_at.replaceAll('-', '.') }}</span>
      <span class="tag" :class="{ 'tag-due': variant === 'urgent', 'tag-info': notice.d_day === null, 'tag-closed': notice.d_day < 0 }">{{ tag }}</span>
    </div>
    <span class="card-title">{{ notice.title }}</span>
    <span v-if="notice.also?.length" class="small">{{ notice.also.join(', ') }}에도 올라온 공지</span>
    <div class="card-foot">
      <span class="reason" v-if="notice.match === 'match'"><Icon name="check" :size="14" :width="2.4" />{{ notice.reason }}</span>
      <span class="small" v-else>{{ notice.reason }}</span>
      <span class="more">자세히 ›</span>
    </div>
  </RouterLink>
</template>
