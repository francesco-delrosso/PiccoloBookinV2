<template>
  <div class="max-w-5xl mx-auto p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-gray-800">Calendario Disponibilita</h1>
      <div class="flex gap-2">
        <button @click="save" :disabled="saving"
          class="px-5 py-2 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary-dark transition-colors disabled:opacity-50">
          {{ saving ? 'Salvataggio...' : 'Salva' }}
        </button>
      </div>
    </div>

    <div v-if="toast.show" class="mb-4 px-4 py-3 rounded-lg text-sm font-medium"
      :class="toast.type === 'error' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'">
      {{ toast.message }}
    </div>

    <p class="text-sm text-gray-500 mb-4">
      Clicca sulle date per segnarle come <span class="font-semibold text-red-600">chiuse</span>.
      Le richieste dal sito per date chiuse verranno <strong>rifiutate automaticamente</strong>.
    </p>

    <!-- Month navigation -->
    <div class="flex items-center gap-4 mb-4">
      <button @click="prevMonths" class="px-3 py-1.5 rounded-lg border border-border hover:bg-gray-50 text-sm">&larr;</button>
      <span class="text-sm font-semibold text-gray-700">
        {{ monthLabel(startMonth) }} — {{ monthLabel(startMonth + 2) }}
      </span>
      <button @click="nextMonths" class="px-3 py-1.5 rounded-lg border border-border hover:bg-gray-50 text-sm">&rarr;</button>
    </div>

    <!-- 3-month calendar grid -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div v-for="offset in [0, 1, 2]" :key="offset" class="bg-surface rounded-xl shadow-sm border border-border p-4">
        <h3 class="text-sm font-bold text-center text-gray-700 mb-3">{{ monthLabel(startMonth + offset) }}</h3>
        <div class="grid grid-cols-7 gap-0.5 text-center text-xs">
          <!-- Day headers -->
          <div v-for="d in ['Lu','Ma','Me','Gi','Ve','Sa','Do']" :key="d" class="font-semibold text-gray-400 py-1">{{ d }}</div>
          <!-- Day cells -->
          <div
            v-for="(day, di) in monthDays(startMonth + offset)"
            :key="di"
            @click="day.date && toggleDate(day.date)"
            class="relative py-1.5 rounded cursor-pointer transition-colors select-none"
            :class="dayClass(day)"
          >
            {{ day.num || '' }}
            <span v-if="day.date && bookingDates[day.date]"
              class="absolute bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full"
              :class="closedDates.has(day.date) ? 'bg-white/60' : 'bg-green-500'"
            ></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Prossima disponibilita -->
    <div class="mt-6 bg-surface rounded-xl shadow-sm border border-border p-5">
      <h3 class="text-sm font-bold text-gray-700 mb-3">Prossima disponibilita</h3>
      <p class="text-xs text-gray-500 mb-3">Questa data viene usata nelle email di rifiuto automatico. Se vuota, viene calcolata dal calendario.</p>
      <div class="flex items-center gap-3">
        <input type="date" v-model="disponibileDa"
          class="px-3 py-2 rounded-lg border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
        <button v-if="disponibileDa" @click="disponibileDa = ''"
          class="text-xs text-gray-400 hover:text-red-500">Svuota (usa calcolo automatico)</button>
      </div>
    </div>

    <!-- Closed ranges summary -->
    <div v-if="closedRanges.length" class="mt-4 bg-surface rounded-xl shadow-sm border border-border p-5">
      <h3 class="text-sm font-bold text-gray-700 mb-3">Periodi chiusi ({{ closedDates.size }} giorni)</h3>
      <div class="flex flex-wrap gap-2">
        <div v-for="(range, ri) in closedRanges" :key="ri"
          class="flex items-center gap-2 px-3 py-1.5 bg-red-50 text-red-700 rounded-lg text-xs font-medium border border-red-200">
          <span>{{ formatDate(range.da) }} &rarr; {{ formatDate(range.a) }}</span>
          <button @click="removeRange(ri)" class="text-red-400 hover:text-red-600">&times;</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getImpostazioni, updateImpostazione } from '../api'
import { usePrenotazioniStore } from '../stores/prenotazioni'

const store = usePrenotazioniStore()

const closedDates = ref(new Set())
const disponibileDa = ref('')
const saving = ref(false)
const toast = ref({ show: false, message: '', type: 'success' })
let toastTimer = null

const now = new Date()
const startMonth = ref(now.getFullYear() * 12 + now.getMonth())

function showToast(message, type = 'success') {
  toast.value = { show: true, message, type }
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value.show = false }, 3000)
}

// Build set of dates that have bookings (arrivo → partenza ranges)
const bookingDates = computed(() => {
  const dates = {}
  for (const p of (store.list || [])) {
    if (!p.data_arrivo || p.stato === 'Rifiutata') continue
    const start = new Date(p.data_arrivo)
    const end = p.data_partenza ? new Date(p.data_partenza) : new Date(start.getTime() + 86400000)
    const cur = new Date(start)
    while (cur < end) {
      const key = cur.toISOString().slice(0, 10)
      dates[key] = (dates[key] || 0) + 1
      cur.setDate(cur.getDate() + 1)
    }
  }
  return dates
})

function prevMonths() { startMonth.value -= 3 }
function nextMonths() { startMonth.value += 3 }

function monthLabel(monthIndex) {
  const y = Math.floor(monthIndex / 12)
  const m = monthIndex % 12
  return new Date(y, m).toLocaleDateString('it-IT', { month: 'long', year: 'numeric' })
}

function monthDays(monthIndex) {
  const y = Math.floor(monthIndex / 12)
  const m = monthIndex % 12
  const firstDay = new Date(y, m, 1)
  const lastDay = new Date(y, m + 1, 0)

  // Monday=0 ... Sunday=6
  let startDow = firstDay.getDay() - 1
  if (startDow < 0) startDow = 6

  const days = []
  // Empty slots before first day
  for (let i = 0; i < startDow; i++) {
    days.push({ num: null, date: null })
  }
  // Actual days
  for (let d = 1; d <= lastDay.getDate(); d++) {
    const date = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    days.push({ num: d, date })
  }
  return days
}

function toggleDate(date) {
  if (closedDates.value.has(date)) {
    closedDates.value.delete(date)
  } else {
    closedDates.value.add(date)
  }
  // Force reactivity
  closedDates.value = new Set(closedDates.value)
}

function dayClass(day) {
  if (!day.date) return 'cursor-default'
  const today = new Date().toISOString().slice(0, 10)
  const isClosed = closedDates.value.has(day.date)
  const isToday = day.date === today
  const isPast = day.date < today

  if (isClosed) return 'bg-red-500 text-white font-bold hover:bg-red-600'
  if (isToday) return 'bg-primary/20 text-primary font-bold hover:bg-red-100'
  if (isPast) return 'text-gray-300 hover:bg-red-50'
  return 'text-gray-700 hover:bg-red-50'
}

// Convert Set of dates → sorted array of {da, a} ranges
const closedRanges = computed(() => {
  const sorted = [...closedDates.value].sort()
  if (!sorted.length) return []

  const ranges = []
  let da = sorted[0]
  let prev = sorted[0]

  for (let i = 1; i < sorted.length; i++) {
    const prevDate = new Date(prev)
    prevDate.setDate(prevDate.getDate() + 1)
    const nextExpected = prevDate.toISOString().slice(0, 10)

    if (sorted[i] === nextExpected) {
      prev = sorted[i]
    } else {
      ranges.push({ da, a: prev })
      da = sorted[i]
      prev = sorted[i]
    }
  }
  ranges.push({ da, a: prev })
  return ranges
})

function removeRange(ri) {
  const range = closedRanges.value[ri]
  const start = new Date(range.da)
  const end = new Date(range.a)
  const current = new Date(start)
  while (current <= end) {
    closedDates.value.delete(current.toISOString().slice(0, 10))
    current.setDate(current.getDate() + 1)
  }
  closedDates.value = new Set(closedDates.value)
}

function formatDate(d) {
  return new Date(d).toLocaleDateString('it-IT', { day: '2-digit', month: 'short' })
}

// Load/Save
onMounted(async () => {
  if (!store.list.length) await store.fetchAll()
  try {
    const { data } = await getImpostazioni()
    const row = data.find(s => s.chiave === 'date_chiuse')
    if (row && row.valore) {
      const dates = JSON.parse(row.valore)
      closedDates.value = new Set(dates)
    }
    const dispRow = data.find(s => s.chiave === 'disponibile_da')
    if (dispRow && dispRow.valore) {
      disponibileDa.value = dispRow.valore
    }
  } catch { /* ignore */ }
})

async function save() {
  saving.value = true
  try {
    const sorted = [...closedDates.value].sort()
    await updateImpostazione({ chiave: 'date_chiuse', valore: JSON.stringify(sorted) })
    await updateImpostazione({ chiave: 'disponibile_da', valore: disponibileDa.value || '' })
    showToast('Calendario salvato')
  } catch (e) {
    showToast('Errore salvataggio', 'error')
  } finally {
    saving.value = false
  }
}
</script>
