<template>
  <div class="bg-surface rounded-xl shadow-sm border border-border p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-xl font-semibold">
          <template v-if="p.nome || p.cognome">
            {{ [p.nome, p.cognome].filter(Boolean).join(' ') }}
          </template>
          <span v-else class="italic text-gray-400">Senza nome</span>
        </h2>
        <p class="text-sm text-gray-500 mt-0.5">{{ p.email }}</p>
      </div>
      <span
        class="inline-flex items-center gap-1 text-sm font-medium px-3 py-1 rounded-full"
        :class="statoClass(p.stato)"
      >
        <span v-if="p.stato === 'Nuova Risposta'" class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
        {{ p.stato }}
      </span>
    </div>

    <!-- Editable Fields Grid -->
    <div class="grid grid-cols-2 gap-4 mb-4">
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Nome</label>
        <input v-model="form.nome" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Cognome</label>
        <input v-model="form.cognome" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Email</label>
        <input v-model="form.email" type="email" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Telefono</label>
        <input v-model="form.telefono" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Data arrivo</label>
        <input v-model="form.data_arrivo" type="date" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Data partenza</label>
        <input v-model="form.data_partenza" type="date" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Adulti</label>
        <input v-model.number="form.adulti" type="number" min="0" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Bambini</label>
        <input v-model.number="form.bambini" type="number" min="0" class="field-input" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Posto per</label>
        <select v-model="form.posto_per" class="field-input">
          <option :value="null">--</option>
          <option value="tenda">Tenda</option>
          <option value="camper">Camper</option>
          <option value="caravan">Caravan</option>
          <option value="bungalow">Bungalow</option>
        </select>
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Tipo richiesta</label>
        <select v-model="form.tipo_richiesta" class="field-input">
          <option value="Prenotazione">Prenotazione</option>
          <option value="Contatto">Contatto</option>
        </select>
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Lingua suggerita</label>
        <select v-model="form.lingua_suggerita" class="field-input">
          <option v-for="l in lingue" :key="l" :value="l">{{ l }}</option>
        </select>
      </div>
    </div>

    <!-- Cost calculation -->
    <div class="mb-6 p-4 bg-gray-50 rounded-lg border border-border">
      <div class="flex items-center gap-3 mb-3">
        <h3 class="text-sm font-semibold text-gray-700">Costo e Caparra</h3>
        <button
          @click="calcola"
          :disabled="!canCalcola"
          class="px-3 py-1 text-xs font-medium rounded-lg bg-warm text-white hover:bg-warm-dark transition-colors disabled:opacity-40"
        >
          Calcola
        </button>
      </div>

      <!-- Breakdown -->
      <div v-if="breakdown.length" class="mb-3 text-xs space-y-1">
        <div v-for="(line, i) in breakdown" :key="i" class="flex justify-between text-gray-600">
          <span>{{ line.label }}</span>
          <span class="font-medium">&euro; {{ line.amount.toFixed(2) }}</span>
        </div>
        <div class="flex justify-between pt-1 border-t border-border text-sm font-bold text-gray-800">
          <span>Totale</span>
          <span>&euro; {{ costoCalcolato.toFixed(2) }}</span>
        </div>
        <div class="flex justify-between text-sm font-semibold text-warm-dark">
          <span>Caparra ({{ caparraPerc }}%)</span>
          <span>&euro; {{ caparraCalcolata.toFixed(2) }}</span>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Costo totale (&euro;)</label>
          <input v-model.number="form.costo_totale" type="number" min="0" step="0.01" class="field-input" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Caparra (&euro;)</label>
          <input :value="caparraDisplay" readonly class="field-input bg-gray-100 cursor-not-allowed" />
        </div>
      </div>
    </div>

    <!-- Save Button -->
    <div v-if="isDirty" class="mb-6">
      <button @click="save" :disabled="saving"
        class="px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-50">
        {{ saving ? 'Salvataggio...' : 'Salva modifiche' }}
      </button>
    </div>

    <!-- Action Buttons -->
    <div class="flex items-center gap-2 pt-4 border-t border-border">
      <button @click="$emit('action', 'accetta')"
        class="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors">
        Accetta
      </button>
      <button @click="$emit('action', 'rifiuta')"
        class="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors">
        Rifiuta
      </button>
      <button @click="$emit('action', 'info')"
        class="px-4 py-2 bg-secondary text-white text-sm font-medium rounded-lg hover:bg-secondary-dark transition-colors">
        Info
      </button>
      <button @click="$emit('action', 'elimina')"
        class="ml-auto px-4 py-2 bg-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-300 transition-colors">
        Elimina
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { updatePrenotazione, getPrezzi, getImpostazioni } from '../api'
import { usePrenotazioniStore } from '../stores/prenotazioni'

const props = defineProps({
  prenotazione: { type: Object, default: null },
})
const emit = defineEmits(['action', 'saved'])
const store = usePrenotazioniStore()

const p = computed(() => props.prenotazione || {})
const lingue = ['IT', 'EN', 'DE', 'FR', 'NL', 'ES']
const saving = ref(false)

// Price list + caparra
const listino = ref(null)
const caparraPerc = ref(30)
const breakdown = ref([])
const costoCalcolato = ref(0)

onMounted(async () => {
  try {
    const [prezziRes, settRes] = await Promise.all([getPrezzi(), getImpostazioni()])
    listino.value = prezziRes.data
    const capRow = settRes.data.find(s => s.chiave === 'caparra_percentuale')
    if (capRow) caparraPerc.value = parseInt(capRow.valore) || 30
  } catch { /* ignore */ }
})

const editableKeys = [
  'nome', 'cognome', 'email', 'telefono',
  'data_arrivo', 'data_partenza', 'adulti', 'bambini',
  'posto_per', 'costo_totale', 'tipo_richiesta', 'lingua_suggerita',
]

const form = ref({})

function resetForm() {
  const obj = {}
  for (const k of editableKeys) {
    obj[k] = p.value[k] ?? null
  }
  form.value = obj
  breakdown.value = []
}

watch(() => p.value.id, resetForm, { immediate: true })

const isDirty = computed(() => {
  for (const k of editableKeys) {
    const original = p.value[k] ?? null
    const current = form.value[k] ?? null
    if (String(original) !== String(current)) return true
  }
  return false
})

const canCalcola = computed(() =>
  form.value.data_arrivo && form.value.data_partenza && form.value.adulti > 0 && listino.value
)

const caparraCalcolata = computed(() => (costoCalcolato.value * caparraPerc.value) / 100)

const caparraDisplay = computed(() => {
  const costo = form.value.costo_totale || 0
  return ((costo * caparraPerc.value) / 100).toFixed(2)
})

// --- Season calculation ---

function getSeasonForDate(dateStr) {
  if (!listino.value) return null
  const d = new Date(dateStr)
  for (let si = 0; si < listino.value.stagioni.length; si++) {
    const s = listino.value.stagioni[si]
    for (const periodo of s.periodi) {
      const from = new Date(Array.isArray(periodo) ? periodo[0] : periodo.da)
      const to = new Date(Array.isArray(periodo) ? periodo[1] : periodo.a)
      if (d >= from && d <= to) return si
    }
  }
  return null
}

function nightsPerSeason() {
  const arr = form.value.data_arrivo
  const dep = form.value.data_partenza
  if (!arr || !dep) return {}

  const counts = {}
  const start = new Date(arr)
  const end = new Date(dep)
  const current = new Date(start)

  while (current < end) {
    const dateStr = current.toISOString().slice(0, 10)
    const si = getSeasonForDate(dateStr)
    if (si !== null) {
      counts[si] = (counts[si] || 0) + 1
    } else {
      // Date outside any season — count as first season (fallback)
      counts[0] = (counts[0] || 0) + 1
    }
    current.setDate(current.getDate() + 1)
  }
  return counts
}

function findVoce(keyword) {
  if (!listino.value) return null
  return listino.value.voci.find(v =>
    v.nome.toLowerCase().includes(keyword.toLowerCase())
  )
}

function getPrezzo(voce, seasonIndex) {
  if (!voce || !voce.prezzi) return 0
  return voce.prezzi[seasonIndex] || 0
}

function calcola() {
  if (!listino.value) return

  const nights = nightsPerSeason()
  const adulti = form.value.adulti || 0
  const bambini = form.value.bambini || 0
  const lines = []
  let total = 0

  const adultoVoce = findVoce('adulto')
  const bambinoVoce = findVoce('bambino (3') || findVoce('bambino')
  const piazzolaVoce = findVoce('piazzola con luce') || findVoce('piazzola luce') || findVoce('piazzola')

  for (const [si, notti] of Object.entries(nights)) {
    const seasonName = listino.value.stagioni[si]?.nome || `Stagione ${si}`
    const idx = parseInt(si)

    // Adulti
    if (adulti > 0 && adultoVoce) {
      const px = getPrezzo(adultoVoce, idx)
      const sub = adulti * notti * px
      lines.push({ label: `${notti} notti × ${adulti} adulti × €${px} (${seasonName})`, amount: sub })
      total += sub
    }

    // Bambini
    if (bambini > 0 && bambinoVoce) {
      const px = getPrezzo(bambinoVoce, idx)
      if (px > 0) {
        const sub = bambini * notti * px
        lines.push({ label: `${notti} notti × ${bambini} bambini × €${px} (${seasonName})`, amount: sub })
        total += sub
      }
    }

    // Piazzola
    if (piazzolaVoce) {
      const px = getPrezzo(piazzolaVoce, idx)
      const sub = notti * px
      lines.push({ label: `${notti} notti × piazzola × €${px} (${seasonName})`, amount: sub })
      total += sub
    }
  }

  if (lines.length === 0) {
    lines.push({ label: 'Nessuna notte trovata nelle stagioni configurate', amount: 0 })
  }

  breakdown.value = lines
  costoCalcolato.value = total
  form.value.costo_totale = Math.round(total * 100) / 100
}

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

async function save() {
  saving.value = true
  try {
    const changes = {}
    for (const k of editableKeys) {
      const original = p.value[k] ?? null
      const current = form.value[k] ?? null
      if (String(original) !== String(current)) {
        changes[k] = current
      }
    }
    await updatePrenotazione(p.value.id, changes)
    await store.selectPrenotazione(p.value.id)
    await store.fetchAll()
    emit('saved')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.field-input {
  width: 100%;
  padding: 0.375rem 0.625rem;
  border-radius: 0.5rem;
  border: 1px solid var(--color-border);
  background: white;
  font-size: 0.875rem;
}
.field-input:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(43, 107, 79, 0.15);
  border-color: var(--color-primary);
}
</style>
