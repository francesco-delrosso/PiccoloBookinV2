<template>
  <div class="min-h-screen bg-bg">
    <nav class="bg-primary text-white shadow-md">
      <div class="flex items-center h-14 px-6 gap-8">
        <span class="text-lg font-bold tracking-wide">Piccolo Camping</span>
        <div class="flex gap-1">
          <router-link
            v-for="link in navLinks"
            :key="link.to"
            :to="link.to"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            :class="$route.path === link.to ? 'bg-white/20' : 'hover:bg-white/10'"
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
const navLinks = [
  { to: '/', label: 'Dashboard' },
  { to: '/impostazioni', label: 'Impostazioni' },
  { to: '/prezzi', label: 'Prezzi' },
  { to: '/calendario', label: 'Calendario' },
]
</script>
