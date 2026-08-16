import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import client from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/components/auth/LoginPage.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    name: 'home',
    component: () => import('@/components/home/HomePage.vue'),
    meta: { public: true },
  },
  {
    path: '/read/:shareId',
    name: 'public-reader',
    component: () => import('@/components/read/PublicReaderPage.vue'),
    meta: { public: true },
  },
  {
    path: '/create',
    name: 'create',
    component: () => import('@/components/create/CreateWizard.vue'),
    meta: { public: false },
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/components/profile/ProfilePage.vue'),
    meta: { public: false },
  },
  {
    path: '/world/:novelId',
    component: () => import('@/layouts/DashboardLayout.vue'),
    meta: { public: true },
    redirect: (to) => `/world/${to.params.novelId}/overview`,
    beforeEnter: async (to, _from, next) => {
      try {
        const { data } = await client.get('/novels')
        const exists = (data.novels || []).some((n: any) => n.novel_id === to.params.novelId)
        if (!exists) {
          return next({ name: 'home' })
        }
      } catch {
        // Allow navigation even if check fails
      }
      return next()
    },
    children: [
      { path: 'overview', name: 'overview', component: () => import('@/components/overview/OverviewPage.vue'), meta: { public: true } },
      { path: 'world-view', name: 'world-view', component: () => import('@/components/world/WorldPage.vue'), meta: { public: true } },
      { path: 'characters', name: 'characters', component: () => import('@/components/characters/CharactersPage.vue'), meta: { public: true } },
      { path: 'timeline', name: 'timeline', component: () => import('@/components/timeline/TimelinePage.vue'), meta: { public: true } },
      { path: 'foreshadows', name: 'foreshadows', component: () => import('@/components/foreshadows/ForeshadowsPage.vue'), meta: { public: true } },
      { path: 'chapters', name: 'chapters', component: () => import('@/components/chapters/ChaptersPage.vue'), meta: { public: true } },
      { path: 'publish', name: 'publish', component: () => import('@/components/publish/PublishPage.vue'), meta: { public: false } },
      { path: 'share', name: 'share', component: () => import('@/components/share/ShareManagePage.vue'), meta: { public: false } },
      { path: 'historian', name: 'historian', component: () => import('@/components/historian/HistorianChat.vue'), meta: { public: false } },
      { path: 'tokens', name: 'tokens', component: () => import('@/components/tokens/TokenPage.vue'), meta: { public: false } },
      { path: 'control', name: 'control', component: () => import('@/components/control/ControlPage.vue'), meta: { public: false } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Auth guard: redirect to login when sidecar auth is enabled and user is not authenticated.
// The auth store is initialized on app mount; this guard handles direct navigation after that.
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()

  // Not initialized yet — allow navigation; the target page will call authStore.init()
  if (!authStore.config) {
    return next()
  }

  // Auth disabled or route is public — allow
  if (!authStore.isAuthEnabled || to.meta?.public) {
    return next()
  }

  // Authenticated — allow
  if (authStore.isAuthenticated) {
    return next()
  }

  // Not authenticated — redirect to login
  return next({ name: 'login', query: { redirect: to.fullPath } })
})

export default router
