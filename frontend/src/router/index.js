import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/impostazioni', name: 'Impostazioni', component: () => import('../views/Impostazioni.vue') },
  { path: '/prezzi', name: 'Prezzi', component: () => import('../views/Prezzi.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
