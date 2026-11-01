let userId = null
let sessionChecked = false

export function isLoggedIn() {
  return userId !== null
}

// 로그인 상태는 서버 세션 쿠키가 기준이고, 앱을 열 때 한 번 확인한다.
export async function restoreSession() {
  if (!sessionChecked) {
    sessionChecked = true
    const response = await fetch('/api/auth/me')
    if (response.ok) userId = (await response.json()).id
  }
  return isLoggedIn()
}

async function request(path, options = {}) {
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
    await request('/auth/logout', { method: 'POST' })
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
  feed: () => request(user('/feed')),
  notice: (id) => request(user(`/notices/${id}`)),
  saveSchedule: (id) => request(user(`/notices/${id}/schedule`), { method: 'POST' }),
  removeSchedule: (id) => request(user(`/notices/${id}/schedule`), { method: 'DELETE' }),
  schedule: () => request(user('/schedule')),
  alerts: () => request(user('/alerts')),
  readAlerts: () => request(user('/alerts/read'), { method: 'POST' }),
  icsUrl: () => `/api${user('/calendar.ics')}`,
  application: (id) => request(user(`/notices/${id}/application`)),
  saveApplication: (id, body) => request(user(`/notices/${id}/application`), { method: 'PUT', body: JSON.stringify(body) }),
  applicationFile: (id) => `/api${user(`/notices/${id}/application.txt`)}`,
  me: () => request('/auth/me'),
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
