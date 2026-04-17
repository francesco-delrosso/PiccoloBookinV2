<template>
  <div class="flex flex-col h-full bg-surface">
    <!-- Search bar -->
    <div class="px-3 pt-3 pb-2">
      <div class="relative">
        <svg
          class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
          fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
        >
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.3-4.3" stroke-linecap="round" />
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Cerca per nome o email..."
          class="w-full pl-9 pr-3 py-2 rounded-lg border border-border bg-white text-sm
                 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary
                 placeholder:text-gray-400"
        />
      </div>
    </div>

    <!-- Filters + date -->
    <div class="px-3 pb-2 flex items-center gap-2">
      <div class="flex gap-1 flex-1 min-w-0">
        <button
          v-for="f in filterOptions"
          :key="f.key"
          @click="activeFilter = f.key"
          class="px-2 py-1 rounded text-[11px] font-medium transition-colors truncate"
          :class="activeFilter === f.key
            ? 'bg-primary text-white'
            : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
        >
          {{ f.label }}
          <span v-if="filterCounts[f.key] > 0" class="ml-0.5 opacity-70">{{ filterCounts[f.key] }}</span>
        </button>
      </div>
      <input
        v-model="dateFilter"
        type="month"
        class="w-28 px-1.5 py-1 rounded border border-border bg-white text-[11px] text-gray-500 shrink-0
               focus:outline-none focus:ring-1 focus:ring-primary/30"
      />
    </div>

    <!-- Separator -->
    <div class="h-px bg-border"></div>

    <!-- Booking list -->
    <div class="flex-1 overflow-y-auto">
      <div
        v-if="groupedItems.length === 0"
        class="p-8 text-center text-gray-400 text-sm"
      >
        <svg class="w-10 h-10 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 9v.906a2.25 2.25 0 0 1-1.183 1.981l-6.478 3.488M2.25 9v.906a2.25 2.25 0 0 0 1.183 1.981l6.478 3.488m8.839 2.51-4.66-2.51m0 0-1.023-.55a2.25 2.25 0 0 0-2.134 0l-1.022.55m0 0-4.661 2.51m16.5-3.386V6.26c0-.577-.342-1.1-.87-1.33l-7.003-3.04a2.25 2.25 0 0 0-1.754 0l-7.003 3.04c-.528.23-.87.753-.87 1.33v9.394" />
        </svg>
        Nessuna prenotazione trovata
      </div>

      <template v-for="group in groupedItems" :key="group.label">
        <!-- Day separator -->
        <div class="sticky top-0 z-10 px-3 py-1.5 bg-bg/95 backdrop-blur-sm border-b border-border/50">
          <span class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
            {{ group.label }}
          </span>
        </div>

        <!-- List items -->
        <div
          v-for="pren in group.items"
          :key="pren.id"
          class="relative flex items-start gap-3 px-3 py-2.5 cursor-pointer transition-all duration-150
                 border-l-[3px] border-b border-b-border/50"
          :class="store.selected?.id === pren.id
            ? 'border-l-secondary bg-secondary/5'
            : 'border-l-transparent hover:bg-gray-50/80'"
          @click="$emit('select', pren.id)"
        >
          <!-- Status dot -->
          <div class="flex-shrink-0 mt-1.5">
            <span
              class="block w-2.5 h-2.5 rounded-full"
              :class="dotClass(pren.stato)"
            ></span>
          </div>

          <!-- Content -->
          <div class="flex-1 min-w-0">
            <div class="flex items-baseline justify-between gap-2">
              <span
                class="text-sm truncate"
                :class="isUnread(pren.stato) ? 'font-bold text-gray-900' : 'font-medium text-gray-700'"
              >
                <template v-if="pren.nome || pren.cognome">
                  {{ [pren.nome, pren.cognome].filter(Boolean).join(' ') }}
                </template>
                <span v-else class="text-gray-500">{{ pren.email || 'Senza nome' }}</span>
              </span>
              <span class="flex-shrink-0 text-[11px] text-gray-400 tabular-nums">
                {{ formatSmartDate(pren.data_ricezione) }}
              </span>
            </div>
            <p class="mt-0.5 text-xs text-gray-400 truncate leading-relaxed">
              {{ previewText(pren) }}
            </p>
          </div>
        </div>
      </template>
    </div>

    <!-- Footer bar -->
    <div class="flex items-center justify-between px-3 py-2 border-t border-border bg-bg/80">
      <span class="text-[11px] text-gray-400">
        {{ localFiltered.length }} risultat{{ localFiltered.length === 1 ? 'o' : 'i' }}
      </span>
      <div class="flex gap-2">
        <button
          @click="exportCSV"
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-medium
                 text-gray-500 bg-white border border-border hover:border-gray-300
                 hover:text-gray-700 transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
          CSV
        </button>
        <button
          @click="printList"
          class="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-medium
                 text-gray-500 bg-white border border-border hover:border-gray-300
                 hover:text-gray-700 transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0 1 10.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0 .229 2.523a1.125 1.125 0 0 1-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0 0 21 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 0 0-1.913-.247M6.34 18H5.25A2.25 2.25 0 0 1 3 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 0 1 1.913-.247m10.5 0a48.536 48.536 0 0 0-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5Zm-3 0h.008v.008H15V10.5Z" />
          </svg>
          Stampa
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { usePrenotazioniStore } from '../stores/prenotazioni'

defineEmits(['select'])

const store = usePrenotazioniStore()

// --- Local filter state ---
const searchQuery = ref('')
const activeFilter = ref('tutti')
const dateFilter = ref('')

const filterOptions = [
  { key: 'tutti', label: 'Tutti' },
  { key: 'da_gestire', label: 'Da gestire' },
  { key: 'confermate', label: 'Confermate' },
  { key: 'rifiutate', label: 'Rifiutate' },
]

const DA_GESTIRE_STATI = ['Nuova', 'Nuova Risposta', 'In lavorazione', 'Attesa Bonifico']

// --- Filter counts ---
const filterCounts = computed(() => {
  const list = store.list || []
  return {
    tutti: list.length,
    da_gestire: list.filter(p => DA_GESTIRE_STATI.includes(p.stato)).length,
    confermate: list.filter(p => p.stato === 'Confermata').length,
    rifiutate: list.filter(p => p.stato === 'Rifiutata').length,
  }
})

// --- Local computed filtered list ---
const localFiltered = computed(() => {
  let items = store.list || []

  // Status filter
  if (activeFilter.value === 'da_gestire') {
    items = items.filter(p => DA_GESTIRE_STATI.includes(p.stato))
  } else if (activeFilter.value === 'confermate') {
    items = items.filter(p => p.stato === 'Confermata')
  } else if (activeFilter.value === 'rifiutate') {
    items = items.filter(p => p.stato === 'Rifiutata')
  }

  // Search filter
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    items = items.filter(p =>
      (p.nome && p.nome.toLowerCase().includes(q)) ||
      (p.cognome && p.cognome.toLowerCase().includes(q)) ||
      (p.email && p.email.toLowerCase().includes(q))
    )
  }

  // Date filter (month/year on data_arrivo)
  if (dateFilter.value) {
    // dateFilter is "YYYY-MM"
    items = items.filter(p => {
      if (!p.data_arrivo) return false
      return p.data_arrivo.startsWith(dateFilter.value)
    })
  }

  // Sort by data_ricezione descending (newest first)
  return [...items].sort((a, b) => {
    const da = a.data_ricezione ? new Date(a.data_ricezione).getTime() : 0
    const db = b.data_ricezione ? new Date(b.data_ricezione).getTime() : 0
    return db - da
  })
})

// --- Group items by day ---
const groupedItems = computed(() => {
  const groups = []
  let currentLabel = null
  let currentGroup = null

  for (const pren of localFiltered.value) {
    const label = dayLabel(pren.data_ricezione)
    if (label !== currentLabel) {
      currentLabel = label
      currentGroup = { label, items: [] }
      groups.push(currentGroup)
    }
    currentGroup.items.push(pren)
  }

  return groups
})

// --- Helpers ---
function dayLabel(dateStr) {
  if (!dateStr) return 'Senza data'
  const d = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.round((today - target) / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'Oggi'
  if (diffDays === 1) return 'Ieri'
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'long', year: 'numeric' })
}

function formatSmartDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())

  if (target.getTime() === today.getTime()) {
    return d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
  }
  const months = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']
  return `${d.getDate()} ${months[d.getMonth()]}`
}

function dotClass(stato) {
  const map = {
    'Nuova': 'bg-blue-500',
    'Nuova Risposta': 'bg-blue-500 ring-2 ring-blue-200',
    'In lavorazione': 'bg-yellow-500',
    'Attesa Bonifico': 'bg-orange-500',
    'Confermata': 'bg-green-500',
    'Rifiutata': 'bg-red-500',
  }
  return map[stato] || 'bg-gray-400'
}

function isUnread(stato) {
  return stato === 'Nuova' || stato === 'Nuova Risposta'
}

function previewText(pren) {
  // Use messaggi first message if available, otherwise tipo_richiesta
  if (pren.messaggi && pren.messaggi.length > 0) {
    const first = pren.messaggi[0]
    const text = first.testo_tradotto || first.testo || ''
    return text.replace(/\s+/g, ' ').trim()
  }
  if (pren.tipo_richiesta) {
    const parts = []
    parts.push(pren.tipo_richiesta)
    if (pren.data_arrivo) parts.push(`Arrivo: ${pren.data_arrivo}`)
    if (pren.posto_per) parts.push(pren.posto_per)
    return parts.join(' - ')
  }
  return pren.email || ''
}

// --- CSV export ---
function exportCSV() {
  const headers = [
    'Nome', 'Cognome', 'Email', 'Telefono', 'Stato', 'Tipo',
    'Arrivo', 'Partenza', 'Adulti', 'Bambini', 'Posto per', 'Costo', 'Data ricezione'
  ]
  const rows = localFiltered.value.map(p => [
    p.nome || '',
    p.cognome || '',
    p.email || '',
    p.telefono || '',
    p.stato || '',
    p.tipo_richiesta || '',
    p.data_arrivo || '',
    p.data_partenza || '',
    p.adulti ?? '',
    p.bambini ?? '',
    p.posto_per || '',
    p.costo_totale ?? '',
    p.data_ricezione || '',
  ])

  const escape = (val) => {
    const s = String(val)
    if (s.includes(',') || s.includes('"') || s.includes('\n')) {
      return '"' + s.replace(/"/g, '""') + '"'
    }
    return s
  }

  const csv = [
    headers.map(escape).join(','),
    ...rows.map(r => r.map(escape).join(','))
  ].join('\n')

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `prenotazioni_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function printList() {
  window.print()
}
</script>
