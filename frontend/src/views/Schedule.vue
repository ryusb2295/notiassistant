<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import { dayOfMonth, dDayLabel, weekday } from '../format'

const WEEK = ['일', '월', '화', '수', '목', '금', '토']
const now = new Date()
const year = ref(now.getFullYear())
const month = ref(now.getMonth())
const items = ref([])
const error = ref('')

onMounted(async () => {
  try {
    items.value = await api.schedule()
  } catch (failure) {
    error.value = failure.message
  }
})

function iso(y, m, d) {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

const days = computed(() => {
  const total = new Date(year.value, month.value + 1, 0).getDate()
  const offset = new Date(year.value, month.value, 1).getDay()
  const todayIso = iso(now.getFullYear(), now.getMonth(), now.getDate())
  const cells = Array.from({ length: offset }, (_, index) => ({ key: `blank-${index}` }))
  for (let day = 1; day <= total; day += 1) {
    const date = iso(year.value, month.value, day)
    const hits = items.value.filter((item) => date >= item.date && date <= (item.end_date || item.date))
    cells.push({
      key: date,
      day,
      sun: (offset + day - 1) % 7 === 0,
      today: date === todayIso,
      due: hits.some((item) => item.kind === 'deadline'),
      event: hits.some((item) => item.kind === 'event'),
    })
  }
  return cells
})

const selected = ref(null)

const listed = computed(() => {
  if (selected.value) {
    return items.value.filter((item) => selected.value >= item.date && selected.value <= (item.end_date || item.date))
  }
  return items.value.filter((item) => item.d_day >= 0)
})

const heading = computed(() => {
  if (!selected.value) return '다가오는 일정 · 공지에서 뽑았어요'
  return `${Number(selected.value.slice(5, 7))}월 ${dayOfMonth(selected.value)}일 (${weekday(selected.value)}) 일정`
})

function select(cell) {
  selected.value = selected.value === cell.key ? null : cell.key
}

function move(step) {
  const next = new Date(year.value, month.value + step, 1)
  year.value = next.getFullYear()
  month.value = next.getMonth()
  selected.value = null
}
</script>

<template>
  <header class="head">
    <div class="head-row">
      <div class="month-nav">
        <button class="icon-btn" aria-label="이전 달" @click="move(-1)"><Icon name="back" /></button>
        <h1 class="title-md">{{ year }}년 {{ month + 1 }}월</h1>
        <button class="icon-btn" aria-label="다음 달" @click="move(1)"><Icon name="next" /></button>
      </div>
      <a :href="api.icsUrl()" class="more">캘린더 파일 받기</a>
    </div>
    <div class="cal">
      <span v-for="(name, index) in WEEK" :key="name" class="cal-week" :class="{ sun: index === 0 }">{{ name }}</span>
      <template v-for="cell in days" :key="cell.key">
        <span v-if="!cell.day"></span>
        <button v-else type="button" class="cal-day" :aria-pressed="selected === cell.key" :aria-label="`${month + 1}월 ${cell.day}일`"
          :class="{ sun: cell.sun, has: cell.due || cell.event, event: cell.event, today: cell.today, selected: selected === cell.key }"
          @click="select(cell)">
          <span>{{ cell.day }}</span>
          <div class="cal-dots"><i v-if="cell.due" class="dot-due"></i><i v-if="cell.event" class="dot-event"></i></div>
        </button>
      </template>
    </div>
    <div class="legend">
      <span><i class="dot-due"></i>신청 마감</span>
      <span><i class="dot-event"></i>참여 행사</span>
    </div>
  </header>
  <main class="main">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div class="toggle-row">
      <span class="section-label">{{ heading }}</span>
      <button v-if="selected" class="link-btn" @click="selected = null">전체 보기</button>
    </div>
    <RouterLink v-for="item in listed" :key="item.id" :to="`/notice/${item.notice_id}`" class="card item">
      <div class="item-date"><span class="small">{{ weekday(item.date) }}</span><b>{{ dayOfMonth(item.date) }}</b></div>
      <div class="item-body">
        <span class="item-title">{{ item.title }}</span>
        <span v-if="item.kind === 'deadline'" class="item-due">신청 마감{{ item.d_day >= 0 ? ` · ${dDayLabel(item.d_day)}` : ' · 지남' }}</span>
        <span v-else class="small">참여 행사{{ item.d_day >= 0 ? ` · ${dDayLabel(item.d_day)}` : ' · 지남' }}</span>
      </div>
    </RouterLink>
    <p v-if="!listed.length" class="empty">{{ selected ? '일정이 없습니다' : '공지에서 일정을 추가하면 여기에 모여요' }}</p>
  </main>
</template>
