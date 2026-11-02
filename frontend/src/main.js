import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import { restoreSession } from './api'
import Account from './views/Account.vue'
import Admin from './views/Admin.vue'
import Alerts from './views/Alerts.vue'
import Applications from './views/Applications.vue'
import Apply from './views/Apply.vue'
import Ask from './views/Ask.vue'
import Attachment from './views/Attachment.vue'
import Boards from './views/Boards.vue'
import Detail from './views/Detail.vue'
import Feed from './views/Feed.vue'
import Me from './views/Me.vue'
import Onboarding from './views/Onboarding.vue'
import Privacy from './views/Privacy.vue'
import Profile from './views/Profile.vue'
import Recommend from './views/Recommend.vue'
import Schedule from './views/Schedule.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Feed, meta: { nav: true } },
    { path: '/start', component: Onboarding, meta: { public: true } },
    { path: '/privacy', component: Privacy, meta: { open: true } },
    { path: '/recommend', component: Recommend },
    { path: '/notice/:id', component: Detail, props: true },
    { path: '/notice/:id/apply', component: Apply, props: true },
    { path: '/admin', component: Admin },
    { path: '/file/:fileId', component: Attachment, props: true },
    { path: '/schedule', component: Schedule, meta: { nav: true } },
    { path: '/boards', component: Boards, meta: { nav: true } },
    { path: '/alerts', component: Alerts, meta: { nav: true } },
    { path: '/ask', component: Ask },
    { path: '/me', component: Me, meta: { nav: true } },
    { path: '/me/profile', component: Profile },
    { path: '/me/account', component: Account },
    { path: '/me/applications', component: Applications },
  ],
})

router.beforeEach(async (to) => {
  const loggedIn = await restoreSession()
  if (!to.meta.public && !to.meta.open && !loggedIn) return '/start'
  if (to.meta.public && loggedIn) return '/'
})

const SPLASH_MS = 700
const started = performance.now()

createApp(App).use(router).mount('#app')

router.isReady().finally(() => {
  const splash = document.getElementById('splash')
  if (!splash) return
  setTimeout(() => {
    splash.classList.add('done')
    setTimeout(() => splash.remove(), 300)
  }, Math.max(0, SPLASH_MS - (performance.now() - started)))
})
