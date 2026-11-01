import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import { restoreSession } from './api'
import Admin from './views/Admin.vue'
import Apply from './views/Apply.vue'
import Attachment from './views/Attachment.vue'
import Boards from './views/Boards.vue'
import Detail from './views/Detail.vue'
import Feed from './views/Feed.vue'
import Me from './views/Me.vue'
import Onboarding from './views/Onboarding.vue'
import Privacy from './views/Privacy.vue'
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
    { path: '/me', component: Me, meta: { nav: true } },
  ],
})

router.beforeEach(async (to) => {
  const loggedIn = await restoreSession()
  if (!to.meta.public && !to.meta.open && !loggedIn) return '/start'
  if (to.meta.public && loggedIn) return '/'
})

createApp(App).use(router).mount('#app')
