<script setup>
defineProps({ count: { type: Number, default: 3 } })
</script>

<template>
  <div class="skeleton-list" role="status" aria-label="불러오는 중">
    <div v-for="n in count" :key="n" class="card skeleton">
      <span class="sk sk-short"></span>
      <span class="sk sk-long"></span>
      <span class="sk sk-mid"></span>
    </div>
  </div>
</template>
