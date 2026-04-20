<template>
  <div class="border-b border-border bg-surface">
    <!-- Compact bar (always visible) -->
    <div class="px-4 py-2.5 flex items-center gap-4 cursor-pointer select-none" @click="expanded = !expanded">
      <!-- Status dot -->
      <span class="w-2.5 h-2.5 rounded-full shrink-0" :class="dotClass(p.stato)"></span>
      <!-- Name + email -->
      <div class="min-w-0 shrink-0">
        <span class="font-semibold text-sm text-gray-800">
          {{ [p.nome, p.cognome].filter(Boolean).join(' ') || p.email || 'Senza nome' }}
        </span>
      </div>
      <!-- Stato badge + expand arrow -->
      <div class="ml-auto flex items-center gap-2 shrink-0">
        <span class="text-xs font-semibold px-2 py-0.5 rounded-full" :class="statoClass(p.stato)">{{ p.stato }}</span>
        <svg class="w-4 h-4 text-gray-400 transition-transform" :class="expanded ? 'rotate-180' : ''" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </div>

    <!-- Expanded form -->
    <div v-if="expanded" class="px-4 pb-4 pt-1 border-t border-border bg-gray-50/50">
      <!-- Original message -->
      <div v-if="messaggioCliente" class="mb-3 p-3 bg-white rounded-lg border border-border text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
        {{ messaggioCliente }}
      </div>

      <div class="grid grid-cols-6 gap-3 text-sm">
        <div>
          <label class="lbl">Nome</label>
          <input v-model="form.nome" class="inp" />
        </div>
        <div>
          <label class="lbl">Cognome</label>
          <input v-model="form.cognome" class="inp" />
        </div>
        <div>
          <label class="lbl">Email</label>
          <input v-model="form.email" type="email" class="inp" />
        </div>
        <div>
          <label class="lbl">Telefono</label>
          <input v-model="form.telefono" class="inp" />
        </div>
        <div>
          <label class="lbl">Arrivo</label>
          <input v-model="form.data_arrivo" type="date" class="inp" />
        </div>
        <div>
          <label class="lbl">Partenza</label>
          <input v-model="form.data_partenza" type="date" class="inp" />
        </div>
        <div>
          <label class="lbl">Adulti</label>
          <input v-model.number="form.adulti" type="number" min="0" class="inp" />
        </div>
        <div>
          <label class="lbl">Bambini</label>
          <input v-model.number="form.bambini" type="number" min="0" class="inp" />
        </div>
        <div>
          <label class="lbl">Alloggio</label>
          <select v-model="form.posto_per" class="inp">
            <option :value="null">--</option>
            <option value="tenda">Tenda</option>
            <option value="camper">Camper</option>
            <option value="caravan">Caravan</option>
            <option value="bungalow">Bungalow</option>
          </select>
        </div>
        <div>
          <label class="lbl">Lingua</label>
          <select v-model="form.lingua_suggerita" class="inp">
            <option v-for="l in lingue" :key="l" :value="l">{{ l }}</option>
          </select>
        </div>
        <div>
          <label class="lbl">Tipo</label>
          <select v-model="form.tipo_richiesta" class="inp">
            <option value="Prenotazione">Prenotazione</option>
            <option value="Contatto">Contatto</option>
          </select>
        </div>
        <div>
          <label class="lbl">Costo &euro;</label>
          <div class="flex gap-1">
            <input v-model.number="form.costo_totale" type="number" min="0" step="0.01" class="inp flex-1" />
            <button @click="calcola" :disabled="!canCalcola"
              class="px-2 py-1 text-[10px] font-semibold rounded bg-warm text-white hover:bg-warm-dark disabled:opacity-30">
              Calc
            </button>
          </div>
        </div>
      </div>

      <!-- Cost breakdown -->
      <div v-if="breakdown.length" class="mt-2 p-2 bg-white rounded-lg border border-border text-xs space-y-0.5">
        <div v-for="(line, i) in breakdown" :key="i" class="flex justify-between text-gray-500">
          <span>{{ line.label }}</span>
          <span class="tabular-nums">&euro;{{ line.amount.toFixed(2) }}</span>
        </div>
        <div class="flex justify-between font-bold text-gray-800 pt-1 border-t border-border">
          <span>Totale</span><span class="tabular-nums">&euro;{{ costoCalcolato.toFixed(2) }}</span>
        </div>
      </div>

      <div v-if="isDirty" class="mt-3">
        <button @click="save" :disabled="saving"
          class="px-4 py-1.5 text-xs font-semibold rounded-lg bg-primary text-white hover:bg-primary-dark disabled:opacity-50">
          {{ saving ? '...' : 'Salva' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { updatePrenotazione, getPrezzi, getImpostazioni } from '../api'
import { usePrenotazioniStore } from '../stores/prenotazioni'

const props = defineProps({ prenotazione: { type: Object, default: null } })
const emit = defineEmits(['saved'])
const store = usePrenotazioniStore()

const p = computed(() => props.prenotazione || {})
const lingue = ['IT', 'EN', 'DE', 'FR', 'NL', 'ES']
const saving = ref(false)
const expanded = ref(true)

const primoMessaggio = computed(() => {
  const msgs = p.value.messaggi
  if (!msgs?.length) return null
  return msgs.find(m => m.mittente === 'Cliente') || msgs[0]
})
const messaggioCliente = computed(() => {
  if (!primoMessaggio.value?.testo) return ''
  const match = primoMessaggio.value.testo.match(/Messaggio:\s*([\s\S]*)/)
  return match ? match[1].trim() : primoMessaggio.value.testo
})

// Price
const listino = ref(null)
const caparraPerc = ref(30)
const breakdown = ref([])
const costoCalcolato = ref(0)

onMounted(async () => {
  try {
    const [pr, se] = await Promise.all([getPrezzi(), getImpostazioni()])
    listino.value = pr.data
    const c = se.data.find(s => s.chiave === 'caparra_percentuale')
    if (c) caparraPerc.value = parseInt(c.valore) || 30
    // Auto-calculate after listino loaded
    if (canCalcola.value && !form.value.costo_totale) calcola()
  } catch {}
})

const caparra = computed(() => ((p.value.costo_totale || 0) * caparraPerc.value / 100).toFixed(2))
const numNotti = computed(() => {
  if (!p.value.data_arrivo || !p.value.data_partenza) return 0
  return Math.max(0, Math.round((new Date(p.value.data_partenza) - new Date(p.value.data_arrivo)) / 86400000))
})

const editableKeys = ['nome','cognome','email','telefono','data_arrivo','data_partenza','adulti','bambini','posto_per','costo_totale','tipo_richiesta','lingua_suggerita']
const form = ref({})

function resetForm() {
  const obj = {}
  for (const k of editableKeys) obj[k] = p.value[k] ?? null
  form.value = obj
  breakdown.value = []
  costoCalcolato.value = 0
}
watch(() => p.value.id, () => {
  resetForm()
  // Auto-calculate cost if we have enough data
  nextTick(() => {
    if (canCalcola.value && !form.value.costo_totale) {
      calcola()
    }
  })
}, { immediate: true })

const isDirty = computed(() => editableKeys.some(k => String(p.value[k] ?? '') !== String(form.value[k] ?? '')))
const canCalcola = computed(() => form.value.data_arrivo && form.value.data_partenza && form.value.adulti > 0 && listino.value)

function fmtDate(d) {
  if (!d) return ''
  const dt = new Date(d)
  const months = ['gen','feb','mar','apr','mag','giu','lug','ago','set','ott','nov','dic']
  return `${dt.getDate()} ${months[dt.getMonth()]}`
}

function dotClass(stato) {
  return { 'Nuova': 'bg-blue-500', 'Nuova Risposta': 'bg-blue-500 animate-pulse', 'In lavorazione': 'bg-yellow-500', 'Attesa Bonifico': 'bg-orange-500', 'Confermata': 'bg-green-500', 'Rifiutata': 'bg-red-500' }[stato] || 'bg-gray-400'
}
function statoClass(stato) {
  return { 'Nuova': 'bg-blue-100 text-blue-800', 'Nuova Risposta': 'bg-blue-100 text-blue-800', 'In lavorazione': 'bg-yellow-100 text-yellow-800', 'Attesa Bonifico': 'bg-orange-100 text-orange-800', 'Confermata': 'bg-green-100 text-green-800', 'Rifiutata': 'bg-red-100 text-red-800' }[stato] || 'bg-gray-100 text-gray-800'
}

function calcola() {
  if (!listino.value) return
  const nights = {}
  const start = new Date(form.value.data_arrivo), end = new Date(form.value.data_partenza), cur = new Date(start)
  while (cur < end) {
    const ds = cur.toISOString().slice(0,10)
    let si = 0
    for (let i = 0; i < listino.value.stagioni.length; i++) {
      for (const per of listino.value.stagioni[i].periodi) {
        const f = new Date(Array.isArray(per)?per[0]:per.da), t = new Date(Array.isArray(per)?per[1]:per.a)
        if (cur >= f && cur <= t) { si = i; break }
      }
    }
    nights[si] = (nights[si]||0) + 1
    cur.setDate(cur.getDate()+1)
  }
  const find = kw => listino.value.voci.find(v => v.nome.toLowerCase().includes(kw))
  const aV = find('adulto'), bV = find('bambino (3') || find('bambino'), pV = find('piazzola con luce') || find('piazzola luce') || find('piazzola')
  const lines = []; let total = 0
  for (const [si,n] of Object.entries(nights)) {
    const nm = listino.value.stagioni[si]?.nome||'Stagione', idx = parseInt(si)
    if (aV && form.value.adulti > 0) { const x = form.value.adulti*n*(aV.prezzi[idx]||0); lines.push({label:`${n}n×${form.value.adulti}ad×€${aV.prezzi[idx]||0} (${nm})`,amount:x}); total+=x }
    if (bV && form.value.bambini > 0 && (bV.prezzi[idx]||0)>0) { const x = form.value.bambini*n*(bV.prezzi[idx]||0); lines.push({label:`${n}n×${form.value.bambini}bam×€${bV.prezzi[idx]||0} (${nm})`,amount:x}); total+=x }
    if (pV) { const x = n*(pV.prezzi[idx]||0); lines.push({label:`${n}n×piazzola×€${pV.prezzi[idx]||0} (${nm})`,amount:x}); total+=x }
  }
  breakdown.value = lines; costoCalcolato.value = total; form.value.costo_totale = Math.round(total*100)/100
}

async function save() {
  saving.value = true
  try {
    const changes = {}
    for (const k of editableKeys) if (String(p.value[k]??'') !== String(form.value[k]??'')) changes[k] = form.value[k]
    await updatePrenotazione(p.value.id, changes)
    emit('saved')
  } finally { saving.value = false }
}
</script>

<style scoped>
.lbl { display: block; font-size: 0.65rem; font-weight: 500; color: #9ca3af; margin-bottom: 0.1rem; }
.inp { width: 100%; padding: 0.25rem 0.4rem; border: 1px solid var(--color-border); border-radius: 0.35rem; font-size: 0.8rem; background: white; }
.inp:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 2px rgba(43,107,79,0.1); }
.pill { background: #f3f4f6; padding: 0.1rem 0.4rem; border-radius: 0.25rem; white-space: nowrap; }
</style>
