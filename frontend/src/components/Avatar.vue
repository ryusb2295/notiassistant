<script setup>
import { ref, watch } from 'vue'
import Icon from './Icon.vue'

const props = defineProps({
  src: { type: String, default: '' },
  name: { type: String, default: '' },
  size: { type: Number, default: 48 },
})

const failed = ref(false)
watch(() => props.src, () => { failed.value = false })
</script>

<template>
  <span class="avatar" :style="{ width: `${size}px`, height: `${size}px` }" aria-hidden="true">
    <img v-if="src && !failed" :src="src" alt="" @error="failed = true" />
    <Icon v-else name="user" :size="Math.round(size * 0.5)" :width="1.8" />
  </span>
</template>
