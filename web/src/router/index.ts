import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/components/home/HomePage.vue'),
  },
  {
    path: '/create',
    name: 'create',
    component: () => import('@/components/create/CreateWizard.vue'),
  },
  {
    path: '/world/:novelId',
    component: () => import('@/layouts/DashboardLayout.vue'),
    redirect: (to) => `/world/${to.params.novelId}/overview`,
    children: [
      { path: 'overview', name: 'overview', component: () => import('@/components/overview/OverviewPage.vue') },
      { path: 'world-view', name: 'world-view', component: () => import('@/components/world/WorldPage.vue') },
      { path: 'characters', name: 'characters', component: () => import('@/components/characters/CharactersPage.vue') },
      { path: 'timeline', name: 'timeline', component: () => import('@/components/timeline/TimelinePage.vue') },
      { path: 'foreshadows', name: 'foreshadows', component: () => import('@/components/foreshadows/ForeshadowsPage.vue') },
      { path: 'chapters', name: 'chapters', component: () => import('@/components/chapters/ChaptersPage.vue') },
      { path: 'historian', name: 'historian', component: () => import('@/components/historian/HistorianChat.vue') },
      { path: 'tokens', name: 'tokens', component: () => import('@/components/tokens/TokenPage.vue') },
      { path: 'control', name: 'control', component: () => import('@/components/control/ControlPage.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
