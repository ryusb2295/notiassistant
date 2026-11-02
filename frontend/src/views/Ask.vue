<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import { longDate } from '../format'

const route = useRoute()
const router = useRouter()
const noticeId = computed(() => (route.query.notice ? Number(route.query.notice) : null))
const notice = ref(null)
const messages = ref([])
const input = ref('')
const busy = ref(false)
const list = ref(null)

const suggestions = computed(() => noticeId.value
  ? ['누가 신청할 수 있어?', '언제까지 어떻게 신청해?', '준비물이나 제출 서류 있어?']
  : ['이번 주 마감인 공지 뭐 있어?', '장학금 관련 공지 알려줘', '해커톤이나 공모전 있어?'])

onMounted(async () => {
  if (noticeId.value) {
    try {
      notice.value = await api.notice(noticeId.value)
    } catch {
      notice.value = null
    }
  }
})

async function scrollDown() {
  await nextTick()
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
}

async function send(text = input.value) {
  const question = text.trim()
  if (!question || busy.value) return
  // 직전 대화 몇 개를 함께 보내 "그거 언제야?" 같은 이어지는 질문을 이해하게 한다.
  const history = messages.value.slice(-4).map((m) => ({ role: m.role, text: m.text }))
  const previous = [...messages.value].reverse().find((m) => m.sources?.length)
  const contextIds = previous ? previous.sources.map((s) => s.id) : []
  messages.value.push({ role: 'user', text: question })
  input.value = ''
  busy.value = true
  scrollDown()
  try {
    const result = await api.ask({ question, notice_id: noticeId.value, history, context_ids: contextIds })
    messages.value.push({ role: 'assistant', text: result.answer, sources: noticeId.value ? [] : result.sources })
  } catch (failure) {
    messages.value.push({ role: 'assistant', text: failure.message, error: true })
  } finally {
    busy.value = false
    scrollDown()
  }
}
</script>

<template>
  <header class="head back-head ask-head">
    <button class="icon-btn" aria-label="뒤로" @click="router.back()"><Icon name="back" :size="22" /></button>
    <div class="inner">
      <span class="eyebrow"><Icon name="spark" :size="13" :width="2.4" /> AI 공지비서</span>
      <h1 class="title-sm">{{ noticeId ? (notice?.title || '공지에 물어보기') : '무엇이든 물어보세요' }}</h1>
    </div>
  </header>

  <main class="chat">
    <section v-if="notice" class="chat-context">
      <span class="small">{{ notice.source }}</span>
      <span :class="notice.match === 'match' ? 'reason' : 'small'">
        <Icon v-if="notice.match === 'match'" name="check" :size="14" :width="2.4" />앱 판정: {{ notice.reason }}
      </span>
    </section>

    <div class="bubble bubble-ai">
      <template v-if="noticeId">이 공지의 본문과 첨부파일을 읽고 답해 드릴게요.</template>
      <template v-else>구독하지 않은 게시판까지 공지를 찾아보고 답해 드릴게요.</template>
    </div>

    <template v-for="(message, index) in messages" :key="index">
      <div class="bubble" :class="message.role === 'user' ? 'bubble-me' : ['bubble-ai', { 'bubble-error': message.error }]">{{ message.text }}</div>
      <div v-if="message.sources?.length" class="chat-sources">
        <span class="small">답변에 쓴 공지</span>
        <RouterLink v-for="source in message.sources" :key="source.id" :to="`/notice/${source.id}`" class="chat-source">
          <span class="chat-source-title">{{ source.title }}</span>
          <span class="small">{{ source.source }}<template v-if="source.deadline"> · {{ longDate(source.deadline) }} 마감</template></span>
        </RouterLink>
      </div>
    </template>

    <div v-if="busy" class="bubble bubble-ai typing" role="status" aria-label="답변을 만드는 중"><i></i><i></i><i></i></div>

    <div v-if="!messages.length" class="chat-suggest">
      <button v-for="text in suggestions" :key="text" class="toggle-chip" @click="send(text)">{{ text }}</button>
    </div>
    <p class="small chat-note">AI 답변은 틀릴 수 있어요. 신청 전에는 원문을 꼭 확인해 주세요. 이름, 학과 같은 내 정보는 AI에 보내지 않아요.</p>
  </main>

  <form class="chat-input" @submit.prevent="send()">
    <input v-model="input" class="input" maxlength="300" placeholder="공지에 대해 물어보세요" aria-label="질문 입력" :disabled="busy" />
    <button class="btn btn-small" :disabled="busy || !input.trim()" aria-label="보내기"><Icon name="send" :size="18" /></button>
  </form>
</template>
