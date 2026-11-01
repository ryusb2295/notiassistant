<script setup>
import { computed } from 'vue'
import { api } from '../api'

const props = defineProps({ sources: { type: Array, required: true } })

const groups = computed(() => [
  { label: '내 학과 추천', items: props.sources.filter((s) => s.recommended) },
  { label: '다른 사업단·기관', items: props.sources.filter((s) => !s.recommended) },
])

async function toggle(source) {
  const next = !source.subscribed
  source.subscribed = next
  try {
    await (next ? api.subscribe(source.id) : api.unsubscribe(source.id))
  } catch {
    source.subscribed = !next
  }
}
</script>

<template>
  <template v-for="group in groups" :key="group.label">
    <template v-if="group.items.length">
      <span class="section-label">{{ group.label }}</span>
      <div v-for="source in group.items" :key="source.id" class="card source" :class="{ on: source.subscribed }">
        <div class="source-body">
          <span class="source-name">{{ source.name }}</span>
          <span class="small">{{ source.description }}</span>
        </div>
        <span v-if="source.kind === 'base'" class="small">기본</span>
        <button v-else class="sub-btn" :class="{ on: source.subscribed }" :aria-pressed="source.subscribed"
          @click="toggle(source)">{{ source.subscribed ? '구독 중' : '+ 구독' }}</button>
      </div>
    </template>
  </template>
</template>
