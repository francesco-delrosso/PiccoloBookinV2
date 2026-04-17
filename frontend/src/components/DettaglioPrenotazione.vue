<template>
  <div class="bg-surface rounded-xl shadow-sm border border-border">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-border">
      <div class="min-w-0">
        <h2 class="text-lg font-bold truncate">
          <template v-if="p.nome || p.cognome">{{ [p.nome, p.cognome].filter(Boolean).join(' ') }}</template>
          <span v-else class="italic text-gray-400">Senza nome</span>
        </h2>
        <div class="flex items-center gap-3 mt-0.5 text-sm text-gray-500">
          <span v-if="p.email">{{ p.email }}</span>
          <span v-if="p.telefono" class="text-gray-400">{{ p.telefono }}</span>
        </div>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <span class="text-xs px-2.5 py-1 rounded-full font-semibold"
          :class="p.tipo_richiesta === 'Prenotazione' ? 'bg-warm/15 text-warm-dark' : 'bg-secondary/15 text-secondary-dark'">
          {{ p.tipo_richiesta }}
        </span>
        <span class="text-xs px-2.5 py-1 rounded-full font-semibold inline-flex items-center gap-1" :class="statoClass(p.stato)">
          <span v-if="p.stato === 'Nuova Risposta'" class="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
          {{ p.stato }}
        </span>
      </div>
    </div>

    <div class="p-6 space-y-5">
      <!-- Messaggio originale -->
      <div v-if="primoMessaggio" class="rounded-lg border border-border bg-gray-50/80 p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Messaggio del cliente</span>
          <span class="text-xs text-gray-400">{{ formatDate(primoMessaggio.data_ora) }}</span>
        </div>
        <div class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{{ primoMessaggio.testo }}</div>
      </div>

      <!-- Dati soggiorno -->
      <div>
        <h3 class="section-title">Soggiorno</h3>
        <div class="grid grid-cols-4 gap-3">
          <div>
            <label class="field-label">Arrivo</label>
            <input v-model="form.data_arrivo" type="date" class="field-input" />
          </div>
          <div>
            <label class="field-label">Partenza</label>
            <input v-model="form.data_partenza" type="date" class="field-input" />
          </div>
          <div>
            <label class="field-label">Adulti</label>
            <input v-model.number="form.adulti" type="number" min="0" class="field-input" />
          </div>
          <div>
            <label class="field-label">Bambini</label>
            <input v-model.number="form.bambini" type="number" min="0" class="field-input" />
          </div>
          <div>
            <label class="field-label">Alloggio</label>
            <select v-model="form.posto_per" class="field-input">
              <option :value="null">--</option>
              <option value="tenda">Tenda</option>
              <option value="camper">Camper</option>
              <option value="caravan">Caravan</option>
              <option value="bungalow">Bungalow</option>
            </select>
          </div>
          <div>
            <label class="field-label">Lingua</label>
            <select v-model="form.lingua_suggerita" class="field-input">
              <option v-for="l in lingue" :key="l" :value="l">{{ l }}</option>
            </select>
          </div>
          <div>
            <label class="field-label">Tipo</label>
            <select v-model="form.tipo_richiesta" class="field-input">
              <option value="Prenotazione">Prenotazione</option>
              <option value="Contatto">Contatto</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Contatto -->
      <div>
        <h3 class="section-title">Contatto</h3>
        <div class="grid grid-cols-4 gap-3">
          <div>
            <label class="field-label">Nome</label>
            <input v-model="form.nome" class="field-input" />
          </div>
          <div>
            <label class="field-label">Cognome</label>
            <input v-model="form.cognome" class="field-input" />
          </div>
          <div>
            <label class="field-label">Email</label>
            <input v-model="form.email" type="email" class="field-input" />
          </div>
          <div>
            <label class="field-label">Telefono</label>
            <input v-model="form.telefono" class="field-input" />
          </div>
        </div>
      </div>

      <!-- Costo -->
      <div>
        <div class="flex items-center gap-3 mb-2">
          <h3 class="section-title mb-0">Costo</h3>
          <button @click="calcola" :disabled="!canCalcola"
            class="px-3 py-1 text-xs font-medium rounded-lg bg-warm text-white hover:bg-warm-dark transition-colors disabled:opacity-40">
            Calcola
          </button>
        </div>
        <div v-if="breakdown.length" class="mb-3 p-3 bg-gray-50 rounded-lg text-xs space-y-1">
          <div v-for="(line, i) in breakdown" :key="i" class="flex justify-between text-gray-600">
            <span>{{ line.label }}</span>
            <span class="font-medium tabular-nums">&euro; {{ line.amount.toFixed(2) }}</span>
          </div>
          <div class="flex justify-between pt-1.5 mt-1.5 border-t border-border text-sm font-bold text-gray-800">
            <span>Totale</span>
            <span class="tabular-nums">&euro; {{ costoCalcolato.toFixed(2) }}</span>
          </div>
          <div class="flex justify-between text-sm font-semibold text-warm-dark">
            <span>Caparra ({{ caparraPerc }}%)</span>
            <span class="tabular-nums">&euro; {{ caparraCalcolata.toFixed(2) }}</span>
          </div>
        </div>
        <div class="grid grid-cols-4 gap-3">
          <div>
            <label class="field-label">Totale &euro;</label>
            <input v-model.number="form.costo_totale" type="number" min="0" step="0.01" class="field-input" />
          </div>
          <div>
            <label class="field-label">Caparra {{ caparraPerc }}% &euro;</label>
            <div class="field-input bg-gray-100 font-semibold text-warm-dark">{{ caparraDisplay }}</div>
          </div>
          <div v-if="form.data_arrivo && form.data_partenza" class="col-span-2 flex items-end">
            <span class="text-xs text-gray-400">{{ numNotti }} notti</span>
          </div>
        </div>
      </div>

      <!-- Save -->
      <div v-if="isDirty">
        <button @click="save" :disabled="saving"
          class="px-5 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-50">
          {{ saving ? 'Salvataggio...' : 'Salva modifiche' }}
        </button>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-2 flex-wrap px-6 py-4 border-t border-border bg-gray-50/50 rounded-b-xl">
      <button @click="$emit('action', 'accetta')"
        class="action-btn bg-green-600 hover:bg-green-700 text-white">Accetta</button>
      <button @click="$emit('action', 'accetta_noCaparra')"
        class="action-btn bg-white text-green-700 border border-green-300 hover:bg-green-50">Accetta senza caparra</button>
      <button @click="$emit('action', 'rifiuta')"
        class="action-btn bg-red-600 hover:bg-red-700 text-white">Rifiuta</button>
      <button @click="$emit('action', 'info')"
        class="action-btn bg-secondary hover:bg-secondary-dark text-white">Info</button>
      <button @click="$emit('action', 'elimina')"
        class="action-btn ml-auto bg-white text-gray-500 border border-gray-200 hover:bg-red-50 hover:text-red-600 hover:border-red-200">Elimina</button>
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

// First client message
const primoMessaggio = computed(() => {
  const msgs = p.value.messaggi
  if (!msgs || !msgs.length) return null
  return msgs.find(m => m.mittente === 'Cliente') || msgs[0]
})

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

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
  for (const k of editableKeys) obj[k] = p.value[k] ?? null
  form.value = obj
  breakdown.value = []
}

watch(() => p.value.id, resetForm, { immediate: true })

const isDirty = computed(() => {
  for (const k of editableKeys) {
    if (String(p.value[k] ?? '') !== String(form.value[k] ?? '')) return true
  }
  return false
})

const canCalcola = computed(() =>
  form.value.data_arrivo && form.value.data_partenza && form.value.adulti > 0 && listino.value
)

const caparraCalcolata = computed(() => (costoCalcolato.value * caparraPerc.value) / 100)
const caparraDisplay = computed(() => ((form.value.costo_totale || 0) * caparraPerc.value / 100).toFixed(2))
const numNotti = computed(() => {
  if (!form.value.data_arrivo || !form.value.data_partenza) return 0
  const ms = new Date(form.value.data_partenza) - new Date(form.value.data_arrivo)
  return Math.max(0, Math.round(ms / 86400000))
})

function getSeasonForDate(dateStr) {
  if (!listino.value) return null
  const d = new Date(dateStr)
  for (let si = 0; si < listino.value.stagioni.length; si++) {
    for (const per of listino.value.stagioni[si].periodi) {
      const from = new Date(Array.isArray(per) ? per[0] : per.da)
      const to = new Date(Array.isArray(per) ? per[1] : per.a)
      if (d >= from && d <= to) return si
    }
  }
  return null
}

function calcola() {
  if (!listino.value) return
  const nights = {}
  const start = new Date(form.value.data_arrivo)
  const end = new Date(form.value.data_partenza)
  const cur = new Date(start)
  while (cur < end) {
    const si = getSeasonForDate(cur.toISOString().slice(0, 10)) ?? 0
    nights[si] = (nights[si] || 0) + 1
    cur.setDate(cur.getDate() + 1)
  }

  const find = (kw) => listino.value.voci.find(v => v.nome.toLowerCase().includes(kw))
  const adultoV = find('adulto')
  const bambinoV = find('bambino (3') || find('bambino')
  const piazzolaV = find('piazzola con luce') || find('piazzola luce') || find('piazzola')
  const lines = []
  let total = 0

  for (const [si, n] of Object.entries(nights)) {
    const name = listino.value.stagioni[si]?.nome || 'Stagione'
    const idx = parseInt(si)
    if (adultoV && form.value.adulti > 0) {
      const px = adultoV.prezzi[idx] || 0
      const sub = form.value.adulti * n * px
      lines.push({ label: `${n}n × ${form.value.adulti} adulti × €${px} (${name})`, amount: sub })
      total += sub
    }
    if (bambinoV && form.value.bambini > 0) {
      const px = bambinoV.prezzi[idx] || 0
      if (px > 0) {
        const sub = form.value.bambini * n * px
        lines.push({ label: `${n}n × ${form.value.bambini} bambini × €${px} (${name})`, amount: sub })
        total += sub
      }
    }
    if (piazzolaV) {
      const px = piazzolaV.prezzi[idx] || 0
      lines.push({ label: `${n}n × piazzola × €${px} (${name})`, amount: n * px })
      total += n * px
    }
  }
  if (!lines.length) lines.push({ label: 'Nessuna notte nelle stagioni configurate', amount: 0 })
  breakdown.value = lines
  costoCalcolato.value = total
  form.value.costo_totale = Math.round(total * 100) / 100
}

function statoClass(stato) {
  return {
    'Nuova': 'bg-blue-100 text-blue-800',
    'Nuova Risposta': 'bg-blue-100 text-blue-800',
    'In lavorazione': 'bg-yellow-100 text-yellow-800',
    'Attesa Bonifico': 'bg-orange-100 text-orange-800',
    'Confermata': 'bg-green-100 text-green-800',
    'Rifiutata': 'bg-red-100 text-red-800',
  }[stato] || 'bg-gray-100 text-gray-800'
}

async function save() {
  saving.value = true
  try {
    const changes = {}
    for (const k of editableKeys) {
      if (String(p.value[k] ?? '') !== String(form.value[k] ?? '')) changes[k] = form.value[k]
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
.section-title {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-primary-dark);
  margin-bottom: 0.5rem;
}
.field-label {
  display: block;
  font-size: 0.7rem;
  font-weight: 500;
  color: #9ca3af;
  margin-bottom: 0.2rem;
}
.field-input {
  width: 100%;
  padding: 0.35rem 0.5rem;
  border-radius: 0.4rem;
  border: 1px solid var(--color-border);
  background: white;
  font-size: 0.8rem;
}
.field-input:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(43, 107, 79, 0.15);
  border-color: var(--color-primary);
}
.action-btn {
  padding: 0.4rem 0.85rem;
  font-size: 0.8rem;
  font-weight: 600;
  border-radius: 0.5rem;
  transition: all 0.15s;
}
</style>
