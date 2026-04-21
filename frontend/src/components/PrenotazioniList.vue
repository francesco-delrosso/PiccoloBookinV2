<template>
  <div class="flex flex-col h-full bg-surface overflow-hidden">
    <!-- Toolbar -->
    <div class="px-4 py-3 border-b border-border flex items-center gap-3 shrink-0 flex-wrap">
      <div class="relative flex-1 min-w-[180px]">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" stroke-linecap="round" />
        </svg>
        <input v-model="searchQuery" type="text" placeholder="Cerca nome o email..."
          class="w-full pl-9 pr-3 py-1.5 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 placeholder:text-gray-400" />
      </div>
      <select v-model="activeFilter"
        class="px-3 py-1.5 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30">
        <option v-for="f in filterOptions" :key="f.key" :value="f.key">{{ f.label }} ({{ filterCounts[f.key] }})</option>
      </select>
      <div class="flex gap-1">
        <button @click="exportCSV" class="tb-sm">CSV</button>
        <button @click="window.print()" class="tb-sm">Stampa</button>
      </div>
    </div>

    <!-- Table -->
    <div class="flex-1 overflow-auto">
      <table class="w-full">
        <thead class="bg-gray-50 sticky top-0 z-10">
          <tr class="text-left text-sm text-gray-500 uppercase tracking-wide">
            <th class="px-4 py-3 font-semibold w-8"></th>
            <th class="px-3 py-3 font-semibold cursor-pointer hover:text-gray-700" @click="toggleSort('nome')">
              Nome {{ sortIcon('nome') }}
            </th>
            <th class="px-3 py-3 font-semibold hidden md:table-cell">Email</th>
            <th class="px-3 py-3 font-semibold cursor-pointer hover:text-gray-700" @click="toggleSort('data_arrivo')">
              Arrivo {{ sortIcon('data_arrivo') }}
            </th>
            <th class="px-3 py-3 font-semibold hidden lg:table-cell">Partenza</th>
            <th class="px-3 py-3 font-semibold hidden md:table-cell">Tipo</th>
            <th class="px-3 py-3 font-semibold">Stato</th>
            <th class="px-3 py-3 font-semibold cursor-pointer hover:text-gray-700 text-right" @click="toggleSort('data_ricezione')">
              Data {{ sortIcon('data_ricezione') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="pagedItems.length === 0">
            <td colspan="9" class="px-4 py-12 text-center text-gray-400">Nessuna prenotazione</td>
          </tr>
          <tr v-for="p in pagedItems" :key="p.id"
            @click="$emit('select', p.id)"
            class="border-b border-border/50 cursor-pointer transition-colors"
            :class="store.selected?.id === p.id ? 'bg-secondary/5' : 'hover:bg-gray-50'">
            <td class="px-4 py-3.5">
              <span class="inline-block w-2.5 h-2.5 rounded-full" :class="dotClass(p.stato)"></span>
            </td>
            <td class="px-3 py-3.5 text-sm font-medium" :class="isUnread(p.stato) ? 'text-gray-900 font-bold' : 'text-gray-700'">
              {{ prenName(p) }}
            </td>
            <td class="px-3 py-3.5 text-sm text-gray-500 hidden md:table-cell truncate max-w-[200px]">{{ p.email || '' }}</td>
            <td class="px-3 py-3.5 text-sm text-gray-600 tabular-nums">{{ fmtShort(p.data_arrivo) }}</td>
            <td class="px-3 py-3.5 text-sm text-gray-500 tabular-nums hidden lg:table-cell">{{ fmtShort(p.data_partenza) }}</td>
            <td class="px-3 py-3.5 text-sm hidden md:table-cell">
              <span class="text-xs px-1.5 py-0.5 rounded font-medium"
                :class="p.tipo_richiesta === 'Prenotazione' ? 'bg-warm/10 text-warm-dark' : 'bg-secondary/10 text-secondary-dark'">
                {{ p.tipo_richiesta === 'Prenotazione' ? 'Pren.' : 'Cont.' }}
              </span>
            </td>
            <td class="px-3 py-3.5 text-sm">
              <span class="text-xs px-2 py-0.5 rounded-full font-semibold" :class="statoClass(p.stato)">
                {{ statoShort(p.stato) }}
              </span>
            </td>
            <td class="px-3 py-3.5 text-sm text-right text-xs text-gray-400 tabular-nums">{{ fmtDate(p.data_ricezione) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Footer -->
    <div class="px-4 py-3 border-t border-border bg-bg/80 flex flex-col items-center gap-2 shrink-0">
      <div class="flex items-center gap-1">
        <button @click="page = 1" :disabled="page <= 1" class="pg-btn">&laquo;</button>
        <button @click="page > 1 && page--" :disabled="page <= 1" class="pg-btn">&lsaquo;</button>
        <template v-for="n in visiblePages" :key="n">
          <span v-if="n === '...'" class="px-1.5 text-gray-400 text-sm">...</span>
          <button v-else @click="page = n" class="pg-btn" :class="page === n ? 'bg-primary text-white border-primary font-bold shadow-md' : 'hover:bg-gray-100'">{{ n }}</button>
        </template>
        <button @click="page < totalPages && page++" :disabled="page >= totalPages" class="pg-btn">&rsaquo;</button>
        <button @click="page = totalPages" :disabled="page >= totalPages" class="pg-btn">&raquo;</button>
      </div>
      <span class="text-xs text-gray-400">{{ filtered.length }} risultati</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { usePrenotazioniStore } from '../stores/prenotazioni'

defineEmits(['select'])
const store = usePrenotazioniStore()

const PER_PAGE = 20
const searchQuery = ref('')
const activeFilter = ref('da_gestire')
const page = ref(1)
const sortKey = ref('data_ricezione')
const sortDir = ref('desc')

const DA_GESTIRE = ['Nuova', 'Nuova Risposta', 'In lavorazione', 'Attesa Bonifico']

const filterOptions = [
  { key: 'tutti', label: 'Tutti' },
  { key: 'da_gestire', label: 'Da gestire' },
  { key: 'in_lavorazione', label: 'In lavorazione' },
  { key: 'attesa', label: 'Attesa bonifico' },
  { key: 'confermate', label: 'Confermate' },
  { key: 'rifiutate', label: 'Rifiutate' },
]

const filterCounts = computed(() => {
  const list = store.list || []
  return {
    tutti: list.length,
    da_gestire: list.filter(p => DA_GESTIRE.includes(p.stato)).length,
    in_lavorazione: list.filter(p => p.stato === 'In lavorazione').length,
    attesa: list.filter(p => p.stato === 'Attesa Bonifico').length,
    confermate: list.filter(p => p.stato === 'Confermata').length,
    rifiutate: list.filter(p => p.stato === 'Rifiutata').length,
  }
})

const filtered = computed(() => {
  let items = store.list || []

  // Filter
  if (activeFilter.value === 'da_gestire') items = items.filter(p => DA_GESTIRE.includes(p.stato))
  else if (activeFilter.value === 'in_lavorazione') items = items.filter(p => p.stato === 'In lavorazione')
  else if (activeFilter.value === 'attesa') items = items.filter(p => p.stato === 'Attesa Bonifico')
  else if (activeFilter.value === 'confermate') items = items.filter(p => p.stato === 'Confermata')
  else if (activeFilter.value === 'rifiutate') items = items.filter(p => p.stato === 'Rifiutata')

  // Search
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    items = items.filter(p =>
      (p.nome && p.nome.toLowerCase().includes(q)) ||
      (p.cognome && p.cognome.toLowerCase().includes(q)) ||
      (p.email && p.email.toLowerCase().includes(q))
    )
  }

  // Sort
  return [...items].sort((a, b) => {
    let va = a[sortKey.value] || ''
    let vb = b[sortKey.value] || ''
    if (sortKey.value === 'nome') {
      va = `${a.nome || ''} ${a.cognome || ''}`.trim().toLowerCase()
      vb = `${b.nome || ''} ${b.cognome || ''}`.trim().toLowerCase()
    }
    if (va < vb) return sortDir.value === 'asc' ? -1 : 1
    if (va > vb) return sortDir.value === 'asc' ? 1 : -1
    return 0
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PER_PAGE)))

const visiblePages = computed(() => {
  const total = totalPages.value
  const cur = page.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages = []
  pages.push(1)
  if (cur > 3) pages.push('...')
  for (let i = Math.max(2, cur - 1); i <= Math.min(total - 1, cur + 1); i++) {
    pages.push(i)
  }
  if (cur < total - 2) pages.push('...')
  pages.push(total)
  return pages
})
const pagedItems = computed(() => {
  if (page.value > totalPages.value) page.value = totalPages.value
  const start = (page.value - 1) * PER_PAGE
  return filtered.value.slice(start, start + PER_PAGE)
})

// Reset page when filter changes
import { watch } from 'vue'
watch([activeFilter, searchQuery], () => { page.value = 1 })

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = key === 'nome' ? 'asc' : 'desc'
  }
}

function sortIcon(key) {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? '↑' : '↓'
}

function prenName(p) {
  return [p.nome, p.cognome].filter(Boolean).join(' ') || p.email || 'Senza nome'
}

function isUnread(stato) {
  return stato === 'Nuova' || stato === 'Nuova Risposta'
}

function dotClass(stato) {
  return {
    'Nuova': 'bg-blue-500', 'Nuova Risposta': 'bg-blue-500 ring-2 ring-blue-200',
    'In lavorazione': 'bg-yellow-500', 'Attesa Bonifico': 'bg-orange-500',
    'Confermata': 'bg-green-500', 'Rifiutata': 'bg-red-500',
  }[stato] || 'bg-gray-400'
}

function statoClass(stato) {
  return {
    'Nuova': 'bg-blue-100 text-blue-800', 'Nuova Risposta': 'bg-blue-100 text-blue-800',
    'In lavorazione': 'bg-yellow-100 text-yellow-800', 'Attesa Bonifico': 'bg-orange-100 text-orange-800',
    'Confermata': 'bg-green-100 text-green-800', 'Rifiutata': 'bg-red-100 text-red-800',
  }[stato] || 'bg-gray-100 text-gray-800'
}

function statoShort(stato) {
  return { 'Nuova Risposta': 'Risposta', 'In lavorazione': 'Lavoraz.', 'Attesa Bonifico': 'Bonifico' }[stato] || stato
}

function fmtShort(d) {
  if (!d) return ''
  const months = ['gen','feb','mar','apr','mag','giu','lug','ago','set','ott','nov','dic']
  const dt = new Date(d)
  return `${dt.getDate()} ${months[dt.getMonth()]}`
}

function fmtDate(d) {
  if (!d) return ''
  const dt = new Date(d)
  const now = new Date()
  if (dt.toDateString() === now.toDateString()) {
    return dt.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
  }
  const months = ['gen','feb','mar','apr','mag','giu','lug','ago','set','ott','nov','dic']
  return `${dt.getDate()} ${months[dt.getMonth()]}`
}

function exportCSV() {
  const headers = ['Nome','Cognome','Email','Telefono','Stato','Tipo','Arrivo','Partenza','Adulti','Bambini','Posto','Costo','Data']
  const rows = filtered.value.map(p => [
    p.nome||'', p.cognome||'', p.email||'', p.telefono||'', p.stato||'', p.tipo_richiesta||'',
    p.data_arrivo||'', p.data_partenza||'', p.adulti??'', p.bambini??'', p.posto_per||'', p.costo_totale??'', p.data_ricezione||'',
  ])
  const esc = v => { const s = String(v); return s.includes(',') || s.includes('"') ? `"${s.replace(/"/g,'""')}"` : s }
  const csv = [headers.join(','), ...rows.map(r => r.map(esc).join(','))].join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `prenotazioni_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
}
</script>

<style scoped>
.pg-btn {
  padding: 0.4rem 0.7rem;
  border: 1px solid var(--color-border);
  border-radius: 0.4rem;
  font-size: 0.875rem;
  background: white;
  cursor: pointer;
  transition: all 0.15s;
  min-width: 2rem;
  text-align: center;
}
.pg-btn:hover:not(:disabled) { background: #f3f4f6; }
.pg-btn:disabled { opacity: 0.3; cursor: default; }
.tb-sm {
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: 0.35rem;
  font-size: 0.68rem;
  font-weight: 500;
  color: #9ca3af;
  background: white;
  cursor: pointer;
}
.tb-sm:hover { color: #374151; border-color: #d1d5db; }
</style>
