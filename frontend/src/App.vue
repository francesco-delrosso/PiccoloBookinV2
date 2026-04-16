<template>
  <div class="min-h-screen bg-bg">
    <nav class="bg-primary text-white shadow-lg">
      <div class="flex items-center h-14 px-6 gap-6">
        <router-link to="/" class="flex items-center gap-2 hover:opacity-90 transition-opacity">
          <span class="text-lg font-bold tracking-wide">Piccolo Camping</span>
        </router-link>
        <div class="flex gap-1 ml-4">
          <router-link
            v-for="link in navLinks"
            :key="link.to"
            :to="link.to"
            class="px-4 py-1.5 rounded-lg text-sm font-medium transition-all"
            :class="isActive(link.to) ? 'bg-white/25 shadow-sm' : 'hover:bg-white/10'"
          >
            {{ link.label }}
          </router-link>
        </div>
      </div>
    </nav>
    <router-view />
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()

const navLinks = [
  { to: '/', label: 'Prenotazioni' },
  { to: '/calendario', label: 'Calendario' },
  { to: '/prezzi', label: 'Listino' },
  { to: '/impostazioni', label: 'Impostazioni' },
]

function isActive(path) {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}
</script>
