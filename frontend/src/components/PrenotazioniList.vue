<template>
  <div class="flex flex-col h-full">
    <!-- Search & Filters -->
    <div class="p-4 space-y-3 border-b border-border">
      <input
        v-model="store.filters.search"
        type="text"
        placeholder="Cerca per nome o email..."
        class="w-full px-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
      />
      <div class="flex gap-2">
        <select
          v-model="store.filters.stato"
          class="flex-1 px-2.5 py-1.5 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
        >
          <option value="">Tutti gli stati</option>
          <option v-for="s in stati" :key="s" :value="s">{{ s }}</option>
        </select>
        <select
          v-model="store.filters.tipo"
          class="flex-1 px-2.5 py-1.5 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
        >
          <option value="">Tutti i tipi</option>
          <option value="Prenotazione">Prenotazione</option>
          <option value="Contatto">Contatto</option>
        </select>
      </div>
    </div>

    <!-- Booking List -->
    <div class="flex-1 overflow-y-auto">
      <div
        v-if="store.filtered.length === 0"
        class="p-6 text-center text-gray-400 text-sm"
      >
        Nessuna prenotazione trovata
      </div>
      <div
        v-for="pren in store.filtered"
        :key="pren.id"
        class="px-4 py-3 border-b border-border cursor-pointer transition-colors hover:bg-gray-50"
        :class="store.selected?.id === pren.id ? 'border-l-4 border-l-primary bg-primary/5' : 'border-l-4 border-l-transparent'"
        @click="$emit('select', pren.id)"
      >
        <div class="flex items-start justify-between gap-2 mb-1">
          <span class="font-medium text-sm truncate">
            <template v-if="pren.nome || pren.cognome">
              {{ [pren.nome, pren.cognome].filter(Boolean).join(' ') }}
            </template>
            <span v-else class="italic text-gray-400">Senza nome</span>
          </span>
          <span
            class="shrink-0 inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full"
            :class="statoClass(pren.stato)"
          >
            <span
              v-if="pren.stato === 'Nuova Risposta'"
              class="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"
            ></span>
            {{ pren.stato }}
          </span>
        </div>
        <div class="text-xs text-gray-500 truncate mb-1">{{ pren.email }}</div>
        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-400">{{ formatDate(pren.data_ricezione) }}</span>
          <span
            class="text-xs font-medium px-2 py-0.5 rounded-full"
            :class="tipoClass(pren.tipo_richiesta)"
          >
            {{ pren.tipo_richiesta }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { usePrenotazioniStore } from '../stores/prenotazioni'

defineEmits(['select'])

const store = usePrenotazioniStore()

const stati = [
  'Nuova',
  'Nuova Risposta',
  'In lavorazione',
  'Attesa Bonifico',
  'Confermata',
  'Rifiutata',
]

function statoClass(stato) {
  const map = {
    'Nuova': 'bg-blue-100 text-blue-800',
    'Nuova Risposta': 'bg-blue-100 text-blue-800',
    'In lavorazione': 'bg-yellow-100 text-yellow-800',
    'Attesa Bonifico': 'bg-orange-100 text-orange-800',
    'Confermata': 'bg-green-100 text-green-800',
    'Rifiutata': 'bg-red-100 text-red-800',
  }
  return map[stato] || 'bg-gray-100 text-gray-800'
}

function tipoClass(tipo) {
  if (tipo === 'Prenotazione') return 'bg-warm/10 text-warm-dark'
  if (tipo === 'Contatto') return 'bg-secondary/10 text-secondary-dark'
  return 'bg-gray-100 text-gray-600'
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('it-IT', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}
</script>
