<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  departments: { type: Array, required: true },
  inputId: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue'])

const query = ref(props.modelValue)
const open = ref(false)
const active = ref(0)
const listId = computed(() => `${props.inputId}-list`)

watch(() => props.modelValue, (value) => {
  if (value) query.value = value
})

function score(item, keyword) {
  const name = item.name.toLowerCase()
  if (name === keyword) return 0
  if (name.startsWith(keyword)) return 1
  if (name.includes(keyword)) return 2
  const others = [item.parent, item.college, ...item.aliases].join(' ').toLowerCase()
  return others.includes(keyword) ? 3 : null
}

const results = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  // 이미 고른 학과를 다시 열면 전체 목록을 보여준다.
  if (!keyword || query.value === props.modelValue) return props.departments
  return props.departments
    .map((item) => ({ item, rank: score(item, keyword) }))
    .filter((entry) => entry.rank !== null)
    .sort((a, b) => a.rank - b.rank)
    .map((entry) => entry.item)
})

// 한글 조합 중에도 글자마다 결과가 바뀌도록 v-model 대신 input 이벤트를 쓴다.
function onInput(event) {
  query.value = event.target.value
  open.value = true
  active.value = 0
  if (props.modelValue) emit('update:modelValue', '')
}

function choose(item) {
  query.value = item.name
  open.value = false
  emit('update:modelValue', item.name)
}

function onKeydown(event) {
  if (event.key === 'Escape') {
    open.value = false
  } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    open.value = true
    const step = event.key === 'ArrowDown' ? 1 : -1
    const size = results.value.length || 1
    active.value = (active.value + step + size) % size
  } else if (event.key === 'Enter' && open.value) {
    event.preventDefault()
    if (results.value[active.value]) choose(results.value[active.value])
  }
}

function subtitle(item) {
  return item.parent ? `${item.college} · ${item.parent}` : item.college
}
</script>

<template>
  <div class="picker">
    <input :id="inputId" :value="query" class="input" type="text" role="combobox" autocomplete="off"
      placeholder="학과 이름을 입력하세요" :aria-expanded="open" :aria-controls="listId" aria-autocomplete="list"
      @input="onInput" @focus="open = true" @blur="open = false" @keydown="onKeydown" />
    <ul v-if="open" :id="listId" class="picker-list" role="listbox">
      <li v-for="(item, index) in results" :key="item.name" role="option" class="picker-item"
        :class="{ active: index === active }" :aria-selected="item.name === modelValue"
        @mousedown.prevent="choose(item)" @mouseenter="active = index">
        <span class="picker-name">{{ item.name }}</span>
        <span class="small">{{ subtitle(item) }}</span>
      </li>
      <li v-if="!results.length" class="picker-empty">일치하는 학과가 없습니다</li>
    </ul>
  </div>
</template>
