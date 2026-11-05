let userId = null
let sessionChecked = false
// 서버 없이 보는 목업 빌드. 데이터는 backend/scripts/export_mock.py 로 뽑은 public/mock JSON.
export const MOCK = import.meta.env.VITE_MOCK === '1'

export function isLoggedIn() {
  return userId !== null
}

// 로그인 상태는 서버 세션 쿠키가 기준이고, 앱을 열 때 한 번 확인한다.
export async function restoreSession() {
  if (!sessionChecked) {
    sessionChecked = true
    if (MOCK) {
      userId = 'me'
      return true
    }
    const response = await fetch('/api/auth/me')
    if (response.ok) userId = (await response.json()).id
  }
  return isLoggedIn()
}

async function mockRequest(path, options) {
  const method = options.method ?? 'GET'
  if (path.endsWith('/ask')) throw new Error('목업 버전이라 AI 비서는 답하지 않아요. 공지 둘러보기만 할 수 있어요.')
  const load = async (name) => {
    const response = await fetch(`${import.meta.env.BASE_URL}mock/${name}.json`)
    if (!response.ok) throw new Error('목업에 없는 데이터예요')
    return response.json()
  }
  if (/^\/auth\/(me|login|signup)$/.test(path)) return load('auth_me')
  if (method !== 'GET') throw new Error('목업 버전이라 저장되지 않아요')
  const [base, query = ''] = path.split('?')
  const params = new URLSearchParams(query)
  if (params.get('q')) {
    const squash = (value) => value.replace(/\s+/g, '').toLowerCase()
    const words = params.get('q').split(/\s+/).filter(Boolean).map(squash)
    const source = params.get('source')
    const cards = (await load('all_cards')).filter((c) =>
      (!source || c.source_id === source) && words.every((w) => squash(c.search_text).includes(w)))
    const feed = await load('users_me_feed')
    return { ...feed, urgent: [], mine: cards.filter((c) => c.match === 'match'), others: cards.filter((c) => c.match !== 'match') }
  }
  const name = (base + (query ? `?${query}` : '')).replace(/^\//, '').replaceAll('/', '_').replaceAll('?', '_').replaceAll('=', '-').replaceAll('&', '_')
  const data = await load(name)
  // 첨부 원본은 목업에 없어서 학교 사이트로만 보낸다.
  return base.startsWith('/attachments/') ? { ...data, preview: 'none', personal: true } : data
}

async function request(path, options = {}) {
  if (MOCK) return mockRequest(path, options)
  const response = await fetch(`/api${path}`, {
    headers: typeof options.body === 'string' ? { 'Content-Type': 'application/json' } : undefined,
    ...options,
  })
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth/')) {
      userId = null
      window.location.assign('/start')
    }
    const error = await response.json().catch(() => ({}))
    const failure = new Error(typeof error.detail === 'string' ? error.detail : '요청을 처리하지 못했어요')
    failure.status = response.status
    throw failure
  }
  return response.status === 204 ? null : response.json()
}

const user = (path = '') => `/users/${userId}${path}`

async function enter(path, body) {
  const account = await request(path, { method: 'POST', body: JSON.stringify(body) })
  userId = account.id
  return account
}

export const api = {
  meta: () => request('/meta'),
  signup: (body) => enter('/auth/signup', body),
  login: (body) => enter('/auth/login', body),
  logout: async () => {
    if (!MOCK) await request('/auth/logout', { method: 'POST' })
    userId = null
  },
  changePassword: (body) => request('/auth/password', { method: 'POST', body: JSON.stringify(body) }),
  deleteAccount: async (password) => {
    await request('/auth/delete-account', { method: 'POST', body: JSON.stringify({ password }) })
    userId = null
  },
  user: () => request(user()),
  updateUser: (body) => request(user(), { method: 'PATCH', body: JSON.stringify(body) }),
  sources: () => request(user('/sources')),
  subscribe: (id) => request(user(`/subscriptions/${id}`), { method: 'PUT' }),
  unsubscribe: (id) => request(user(`/subscriptions/${id}`), { method: 'DELETE' }),
  feed: (source, q) => {
    const params = new URLSearchParams()
    if (source) params.set('source', source)
    if (q) params.set('q', q)
    const query = params.toString()
    return request(user(query ? `/feed?${query}` : '/feed'))
  },
  feedback: (id, kind, note = '') => request(user(`/notices/${id}/feedback`), { method: 'POST', body: JSON.stringify({ kind, note }) }),
  adminFeedback: () => request('/admin/feedback'),
  ask: (body) => request(user('/ask'), { method: 'POST', body: JSON.stringify(body) }),
  avatarUrl: (version = '') => `/api${user('/avatar')}?v=${version}`,
  uploadAvatar: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request(user('/avatar'), { method: 'PUT', body: form })
  },
  deleteAvatar: () => request(user('/avatar'), { method: 'DELETE' }),
  notice: (id) => request(user(`/notices/${id}`)),
  saveSchedule: (id) => request(user(`/notices/${id}/schedule`), { method: 'POST' }),
  removeSchedule: (id) => request(user(`/notices/${id}/schedule`), { method: 'DELETE' }),
  schedule: () => request(user('/schedule')),
  alerts: () => request(user('/alerts')),
  readAlerts: (ids) => request(user('/alerts/read'), { method: 'POST', body: JSON.stringify({ ids: ids ?? null }) }),
  deleteAlerts: (ids) => request(user('/alerts/delete'), { method: 'POST', body: JSON.stringify({ ids }) }),
  icsUrl: () => (MOCK ? '#' : `/api${user('/calendar.ics')}`),
  application: (id) => request(user(`/notices/${id}/application`)),
  saveApplication: (id, body) => request(user(`/notices/${id}/application`), { method: 'PUT', body: JSON.stringify(body) }),
  applicationFile: (id) => (MOCK ? '#' : `/api${user(`/notices/${id}/application.txt`)}`),
  me: () => request('/auth/me'),
  summary: () => request(user('/summary')),
  applications: () => request(user('/applications')),
  adminNotices: () => request('/admin/notices'),
  adminPublish: (body) => request('/admin/notices', { method: 'POST', body: JSON.stringify(body) }),
  adminAnalyze: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/admin/analyze', { method: 'POST', body: form })
  },
  attachment: (id) => request(`/attachments/${id}`),
  attachmentText: (id) => request(`/attachments/${id}/text`),
  attachmentFile: (id) => `/api/attachments/${id}/file`,
}
