<template>
  <div class="flex flex-col h-full bg-surface">
    <!-- Search bar -->
    <div class="px-3 pt-3 pb-2">
      <div class="relative">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" stroke-linecap="round" />
        </svg>
        <input v-model="searchQuery" type="text" placeholder="Cerca nome o email..."
          class="w-full pl-9 pr-3 py-2 rounded-lg border border-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 placeholder:text-gray-400" />
      </div>
    </div>

    <div class="h-px bg-border"></div>

    <!-- Sectioned list -->
    <div class="flex-1 overflow-y-auto">
      <div v-if="allFiltered.length === 0" class="p-8 text-center text-gray-400 text-sm">
        Nessuna prenotazione
      </div>

      <!-- NUOVE RISPOSTE -->
      <template v-if="sections.risposte.length">
        <div class="section-header bg-blue-50/80 text-blue-700" @click="collapsed.risposte = !collapsed.risposte">
          <span>Nuove risposte</span>
          <span class="section-count bg-blue-500 text-white">{{ sections.risposte.length }}</span>
          <svg class="section-arrow" :class="collapsed.risposte ? '' : 'rotate-180'" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
        </div>
        <template v-if="!collapsed.risposte">
          <div v-for="p in sections.risposte" :key="p.id" @click="$emit('select', p.id)" class="list-item" :class="store.selected?.id === p.id ? 'border-l-secondary bg-secondary/5' : 'border-l-transparent hover:bg-gray-50'"><div class="flex-1 min-w-0"><div class="flex items-baseline justify-between gap-2"><span class="text-sm truncate" :class="isUnread(p.stato) ? 'font-bold text-gray-900' : 'font-medium text-gray-700'">{{ prenName(p) }}</span><span class="flex-shrink-0 text-[11px] text-gray-400 tabular-nums">{{ fmtDate(p.data_ricezione) }}</span></div><p class="mt-0.5 text-xs text-gray-400 truncate">{{ preview(p) }}</p></div></div>
          <button v-if="hiddenCount('risposte') > 0" @click="showAll.risposte = true" class="show-more" v-if="!showAll.risposte">Mostra altre {{ hiddenCount('risposte') }} piu vecchie</button>
          <button @click="showAll.risposte = false" class="show-more" v-if="showAll.risposte">Mostra meno</button>
        </template>
      </template>

      <!-- DA GESTIRE (Nuove + In lavorazione) -->
      <template v-if="sections.daGestire.length">
        <div class="section-header bg-yellow-50/80 text-yellow-800" @click="collapsed.daGestire = !collapsed.daGestire">
          <span>Da gestire</span>
          <span class="section-count bg-yellow-500 text-white">{{ sections.daGestire.length }}</span>
          <svg class="section-arrow" :class="collapsed.daGestire ? '' : 'rotate-180'" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
        </div>
        <template v-if="!collapsed.daGestire">
          <div v-for="p in sections.daGestire" :key="p.id" @click="$emit('select', p.id)" class="list-item" :class="store.selected?.id === p.id ? 'border-l-secondary bg-secondary/5' : 'border-l-transparent hover:bg-gray-50'"><div class="flex-1 min-w-0"><div class="flex items-baseline justify-between gap-2"><span class="text-sm truncate" :class="isUnread(p.stato) ? 'font-bold text-gray-900' : 'font-medium text-gray-700'">{{ prenName(p) }}</span><span class="flex-shrink-0 text-[11px] text-gray-400 tabular-nums">{{ fmtDate(p.data_ricezione) }}</span></div><p class="mt-0.5 text-xs text-gray-400 truncate">{{ preview(p) }}</p></div></div>
          <button v-if="hiddenCount('daGestire') > 0" @click="showAll.daGestire = true" class="show-more" v-if="!showAll.daGestire">Mostra altre {{ hiddenCount('daGestire') }} piu vecchie</button>
          <button @click="showAll.daGestire = false" class="show-more" v-if="showAll.daGestire">Mostra meno</button>
        </template>
      </template>

      <!-- IN ATTESA BONIFICO -->
      <template v-if="sections.attesa.length">
        <div class="section-header bg-orange-50/80 text-orange-700" @click="collapsed.attesa = !collapsed.attesa">
          <span>In attesa bonifico</span>
          <span class="section-count bg-orange-500 text-white">{{ sections.attesa.length }}</span>
          <svg class="section-arrow" :class="collapsed.attesa ? '' : 'rotate-180'" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
        </div>
        <template v-if="!collapsed.attesa">
          <div v-for="p in sections.attesa" :key="p.id" @click="$emit('select', p.id)" class="list-item" :class="store.selected?.id === p.id ? 'border-l-secondary bg-secondary/5' : 'border-l-transparent hover:bg-gray-50'"><div class="flex-1 min-w-0"><div class="flex items-baseline justify-between gap-2"><span class="text-sm truncate" :class="isUnread(p.stato) ? 'font-bold text-gray-900' : 'font-medium text-gray-700'">{{ prenName(p) }}</span><span class="flex-shrink-0 text-[11px] text-gray-400 tabular-nums">{{ fmtDate(p.data_ricezione) }}</span></div><p class="mt-0.5 text-xs text-gray-400 truncate">{{ preview(p) }}</p></div></div>
          <button v-if="hiddenCount('attesa') > 0" @click="showAll.attesa = true" class="show-more" v-if="!showAll.attesa">Mostra altre {{ hiddenCount('attesa') }}</button>
          <button @click="showAll.attesa = false" class="show-more" v-if="showAll.attesa">Mostra meno</button>
        </template>
      </template>

      <!-- CONFERMATE -->
      <template v-if="sectionsAll.confermate.length">
        <div class="section-header bg-green-50/80 text-green-700" @click="collapsed.confermate = !collapsed.confermate">
          <span>Confermate</span>
          <span class="section-count bg-green-500 text-white">{{ sectionsAll.confermate.length }}</span>
          <svg class="section-arrow" :class="collapsed.confermate ? '' : 'rotate-180'" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
        </div>
        <template v-if="!collapsed.confermate">
          <div v-for="p in sections.confermate" :key="p.id" @click="$emit('select', p.id)" class="list-item" :class="store.selected?.id === p.id ? 'border-l-secondary bg-secondary/5' : 'border-l-transparent hover:bg-gray-50'"><div class="flex-1 min-w-0"><div class="flex items-baseline justify-between gap-2"><span class="text-sm truncate" :class="isUnread(p.stato) ? 'font-bold text-gray-900' : 'font-medium text-gray-700'">{{ prenName(p) }}</span><span class="flex-shrink-0 text-[11px] text-gray-400 tabular-nums">{{ fmtDate(p.data_ricezione) }}</span></div><p class="mt-0.5 text-xs text-gray-400 truncate">{{ preview(p) }}</p></div></div>
          <button v-if="hiddenCount('confermate') > 0" @click="showAll.confermate = true" class="show-more" v-if="!showAll.confermate">Mostra altre {{ hiddenCount('confermate') }}</button>
          <button @click="showAll.confermate = false" class="show-more" v-if="showAll.confermate">Mostra meno</button>
        </template>
      </template>

      <!-- RIFIUTATE -->
      <template v-if="sectionsAll.rifiutate.length">
        <div class="section-header bg-red-50/80 text-red-700" @click="collapsed.rifiutate = !collapsed.rifiutate">
          <span>Rifiutate</span>
          <span class="section-count bg-red-500 text-white">{{ sectionsAll.rifiutate.length }}</span>
          <svg class="section-arrow" :class="collapsed.rifiutate ? '' : 'rotate-180'" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
        </div>
        <template v-if="!collapsed.rifiutate">
          <div v-for="p in sections.rifiutate" :key="p.id" @click="$emit('select', p.id)" class="list-item" :class="store.selected?.id === p.id ? 'border-l-secondary bg-secondary/5' : 'border-l-transparent hover:bg-gray-50'"><div class="flex-1 min-w-0"><div class="flex items-baseline justify-between gap-2"><span class="text-sm truncate" :class="isUnread(p.stato) ? 'font-bold text-gray-900' : 'font-medium text-gray-700'">{{ prenName(p) }}</span><span class="flex-shrink-0 text-[11px] text-gray-400 tabular-nums">{{ fmtDate(p.data_ricezione) }}</span></div><p class="mt-0.5 text-xs text-gray-400 truncate">{{ preview(p) }}</p></div></div>
          <button v-if="hiddenCount('rifiutate') > 0" @click="showAll.rifiutate = true" class="show-more" v-if="!showAll.rifiutate">Mostra altre {{ hiddenCount('rifiutate') }}</button>
          <button @click="showAll.rifiutate = false" class="show-more" v-if="showAll.rifiutate">Mostra meno</button>
        </template>
      </template>
    </div>

    <!-- Footer -->
    <div class="flex items-center justify-between px-3 py-2 border-t border-border bg-bg/80">
      <span class="text-[11px] text-gray-400">{{ allFiltered.length }} risultati</span>
      <div class="flex gap-2">
        <button @click="exportCSV" class="footer-btn">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>
          CSV
        </button>
        <button @click="window.print()" class="footer-btn">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0 1 10.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0 .229 2.523a1.125 1.125 0 0 1-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0 0 21 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 0 0-1.913-.247M6.34 18H5.25A2.25 2.25 0 0 1 3 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 0 1 1.913-.247m10.5 0a48.536 48.536 0 0 0-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5Zm-3 0h.008v.008H15V10.5Z" /></svg>
          Stampa
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { usePrenotazioniStore } from '../stores/prenotazioni'

defineEmits(['select'])
const store = usePrenotazioniStore()

const searchQuery = ref('')
const collapsed = reactive({
  risposte: false,
  daGestire: false,
  attesa: false,
  confermate: true,
  rifiutate: true,
})
const showAll = reactive({
  risposte: false,
  daGestire: false,
  attesa: false,
  confermate: false,
  rifiutate: false,
})

const TWO_WEEKS = 14 * 24 * 60 * 60 * 1000

// Search filter
const allFiltered = computed(() => {
  let items = store.list || []
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    items = items.filter(p =>
      (p.nome && p.nome.toLowerCase().includes(q)) ||
      (p.cognome && p.cognome.toLowerCase().includes(q)) ||
      (p.email && p.email.toLowerCase().includes(q))
    )
  }
  return [...items].sort((a, b) => {
    const da = a.data_ricezione ? new Date(a.data_ricezione).getTime() : 0
    const db = b.data_ricezione ? new Date(b.data_ricezione).getTime() : 0
    return db - da
  })
})

const cutoff = new Date(Date.now() - TWO_WEEKS)

function recentOnly(items, sectionKey) {
  if (showAll[sectionKey] || searchQuery.value) return items
  return items.filter(p => {
    if (!p.data_ricezione) return true
    return new Date(p.data_ricezione) >= cutoff
  })
}

// Split into sections
const sectionsAll = computed(() => {
  const list = allFiltered.value
  return {
    risposte: list.filter(p => p.stato === 'Nuova Risposta'),
    daGestire: list.filter(p => ['Nuova', 'In lavorazione'].includes(p.stato)),
    attesa: list.filter(p => p.stato === 'Attesa Bonifico'),
    confermate: list.filter(p => p.stato === 'Confermata'),
    rifiutate: list.filter(p => p.stato === 'Rifiutata'),
  }
})

const sections = computed(() => ({
  risposte: recentOnly(sectionsAll.value.risposte, 'risposte'),
  daGestire: recentOnly(sectionsAll.value.daGestire, 'daGestire'),
  attesa: recentOnly(sectionsAll.value.attesa, 'attesa'),
  confermate: recentOnly(sectionsAll.value.confermate, 'confermate'),
  rifiutate: recentOnly(sectionsAll.value.rifiutate, 'rifiutate'),
}))

function hiddenCount(sectionKey) {
  return sectionsAll.value[sectionKey].length - sections.value[sectionKey].length
}

// Helpers for list items
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

function preview(p) {
  const parts = [p.tipo_richiesta || '']
  if (p.data_arrivo) parts.push(`Arrivo: ${p.data_arrivo}`)
  if (p.posto_per) parts.push(p.posto_per)
  return parts.join(' - ')
}

function prenName(p) {
  return [p.nome, p.cognome].filter(Boolean).join(' ') || p.email || 'Senza nome'
}

function isUnread(stato) {
  return stato === 'Nuova' || stato === 'Nuova Risposta'
}

// CSV export
function exportCSV() {
  const headers = ['Nome','Cognome','Email','Telefono','Stato','Tipo','Arrivo','Partenza','Adulti','Bambini','Posto','Costo','Data']
  const rows = allFiltered.value.map(p => [
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
.section-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 5;
}
.section-count {
  font-size: 0.6rem;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  font-weight: 700;
}
.section-arrow {
  width: 14px;
  height: 14px;
  margin-left: auto;
  transition: transform 0.15s;
  opacity: 0.5;
}
.footer-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.68rem;
  font-weight: 500;
  color: #9ca3af;
  background: white;
  border: 1px solid var(--color-border);
  transition: all 0.15s;
}
.list-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.625rem 0.75rem;
  cursor: pointer;
  border-left: 3px solid;
  border-bottom: 1px solid rgba(226, 222, 214, 0.5);
  transition: all 0.15s;
}
.show-more {
  display: block;
  width: 100%;
  padding: 0.5rem;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--color-secondary);
  background: var(--color-bg);
  border: none;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  text-align: center;
}
.show-more:hover {
  background: rgba(74, 124, 155, 0.08);
}
.footer-btn:hover {
  color: #374151;
  border-color: #d1d5db;
}
</style>
