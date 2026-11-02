<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  sources: { type: Array, required: true },
  modelValue: { type: String, default: null },
})
const emit = defineEmits(['update:modelValue'])

const rail = ref(null)
let dragStart = null
let moved = false

// PC에서도 휴대폰처럼 마우스로 끌어서 넘길 수 있게 한다.
function onPointerDown(event) {
  if (event.pointerType !== 'mouse') return
  dragStart = { x: event.clientX, left: rail.value.scrollLeft }
  moved = false
}
function onPointerMove(event) {
  if (!dragStart) return
  const distance = event.clientX - dragStart.x
  if (Math.abs(distance) > 4) moved = true
  rail.value.scrollLeft = dragStart.left - distance
}
function onPointerUp() {
  dragStart = null
}
// 끌기를 끝낸 순간의 클릭은 칩 선택으로 치지 않는다.
function onClickCapture(event) {
  if (moved) {
    event.stopPropagation()
    event.preventDefault()
    moved = false
  }
}

function select(id) {
  emit('update:modelValue', props.modelValue === id ? null : id)
}

watch(() => props.modelValue, async () => {
  await nextTick()
  rail.value?.querySelector('[aria-pressed="true"]')?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' })
})
</script>

<template>
  <div class="rail-wrap">
    <div ref="rail" class="rail" role="group" aria-label="게시판별로 보기"
      @pointerdown="onPointerDown" @pointermove="onPointerMove" @pointerup="onPointerUp" @pointerleave="onPointerUp"
      @click.capture="onClickCapture">
      <button class="chip chip-filter" :aria-pressed="modelValue === null" @click="emit('update:modelValue', null)">전체</button>
      <button v-for="source in sources" :key="source.id" class="chip chip-filter" :aria-pressed="modelValue === source.id"
        @click="select(source.id)">{{ source.name }}</button>
      <RouterLink to="/boards" class="chip chip-add">+ 게시판 추가</RouterLink>
    </div>
  </div>
</template>
